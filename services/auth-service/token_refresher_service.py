"""
token_refresher_service.py
--------------------------------------------------------
FastAPI-based Zerodha Kite Token Refresher & Auto-Updater.

Responsibilities:
  ✅ Handle Zerodha OAuth callback → Generate access_token
  ✅ Auto-update .env (KITE_ACCESS_TOKEN, KITE_REFRESH_TOKEN, KITE_REQUEST_TOKEN)
  ✅ Notify ingestion service to reload
  ✅ Expose / and /health endpoints
--------------------------------------------------------
Usage:
    uvicorn token_refresher_service:app --host 0.0.0.0 --port 8018
--------------------------------------------------------
"""

import os
import asyncio
import requests
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from kiteconnect import KiteConnect
from kiteconnect import exceptions as kite_exceptions
from dotenv import load_dotenv
import hashlib
import json
from core.utils.logger import get_logger

# ==============================================================
# 🔹 Environment Setup
# ==============================================================

BASE_DIR = Path(__file__).resolve().parent
DOCKER_ENV_PATH = Path("/app/.env")
LOCAL_ENV_PATH = BASE_DIR.parent.parent / ".env"
ENV_PATH = DOCKER_ENV_PATH if DOCKER_ENV_PATH.exists() else LOCAL_ENV_PATH

if not ENV_PATH.exists():
    raise FileNotFoundError(f"❌ .env file not found at {ENV_PATH}")

load_dotenv(ENV_PATH)
logger = get_logger("token_refresher")
logger.info(f"✅ [ENV] Loaded environment variables from {ENV_PATH}")

# ==============================================================
# 🔹 Configuration
# ==============================================================

KITE_API_KEY = os.getenv("KITE_API_KEY")
KITE_API_SECRET = os.getenv("KITE_API_SECRET")
INGESTION_URL = os.getenv("INGESTION_API", "http://data_service:8080/api/v1/reload")
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*")

# ==============================================================
# 🔹 FastAPI App
# ==============================================================

app = FastAPI(title="Kite Token Refresher API", version="2.0")

# ==============================================================
# 🔹 Helper Functions
# ==============================================================

def safe_update_env_sync(key: str, value: str):
    """Safely update or append key=value in .env (sync, atomic, safe)."""
    try:
        lines = []
        updated = False

        # Read existing lines
        if ENV_PATH.exists():
            with open(ENV_PATH, "r") as f:
                for line in f:
                    if line.startswith(f"{key}="):
                        lines.append(f"{key}={value}\n")
                        updated = True
                    else:
                        lines.append(line)

        if not updated:
            lines.append(f"{key}={value}\n")

        temp_path = ENV_PATH.with_suffix(".tmp")
        with open(temp_path, "w") as f:
            f.writelines(lines)

        os.replace(temp_path, ENV_PATH)
        logger.info(f"✅ [ENV] Updated {key} in .env")

    except Exception as e:
        logger.exception(f"💥 [ENV] Failed to update {key}: {e}")


def trigger_ingestion_reload():
    """Notify data_service to reload tokens."""
    try:
        res = requests.post(INGESTION_URL, timeout=5)
        if res.status_code == 200:
            logger.info("🔄 [RELOAD] Triggered ingestion reload successfully.")
        else:
            logger.warning(f"⚠️ [RELOAD] Ingestion reload returned {res.status_code}")
    except Exception as e:
        logger.warning(f"⚠️ [RELOAD] Failed to notify ingestion: {e}")


def generate_real_access_token(request_token: str):
    """Exchange request_token → access_token using KiteConnect."""
    if not KITE_API_KEY or not KITE_API_SECRET:
        logger.error("Missing KITE_API_KEY or KITE_API_SECRET in .env")
        return None

    kite = KiteConnect(api_key=KITE_API_KEY)
    try:
        logger.info(f"🔑 [KITE] Generating new access token for request_token={request_token[:8]}...")
        session_data = kite.generate_session(request_token, api_secret=KITE_API_SECRET)
        access_token = session_data.get("access_token")
        refresh_token = session_data.get("refresh_token", "")

        # ✅ Update both request & access tokens
        safe_update_env_sync("KITE_REQUEST_TOKEN", request_token)
        safe_update_env_sync("KITE_ACCESS_TOKEN", access_token)
        if refresh_token:
            safe_update_env_sync("KITE_REFRESH_TOKEN", refresh_token)

        logger.info("✅ [TOKEN] Access & Refresh tokens generated and saved.")
        trigger_ingestion_reload()
        return access_token

    except kite_exceptions.TokenException as te:
        logger.error(f"💥 [KITE TOKEN] Invalid request_token: {te}")
        return None
    except Exception as e:
        logger.exception(f"💥 [KITE] Failed to generate access token: {e}")
        return None


# ==============================================================
# 🔹 Routes
# ==============================================================

@app.get("/")
async def root():
    """Return Zerodha OAuth login URL."""
    if not KITE_API_KEY:
        return {"error": "KITE_API_KEY missing in .env"}

    login_url = f"https://kite.zerodha.com/connect/login?api_key={KITE_API_KEY}&v=3"
    return {"login_url": login_url}


@app.get("/callback")
async def kite_callback(request: Request):
    """Handle Zerodha OAuth redirect callback."""
    query = dict(request.query_params)
    request_token = query.get("request_token")
    status = query.get("status")

    if not request_token:
        return JSONResponse({"error": "Missing request_token"}, status_code=400)
    if status != "success":
        return JSONResponse({"error": "Login failed or unauthorized"}, status_code=401)

    logger.info(f"🔑 [CALLBACK] Received request_token={request_token[:8]}...")
    access_token = generate_real_access_token(request_token)

    if not access_token:
        return JSONResponse({"error": "Failed to generate access token"}, status_code=500)

    html = f"""
    <!doctype html>
    <html>
        <head><meta charset="utf-8"><title>Auth Successful</title></head>
        <body>
            <p>✅ Authentication successful. You can close this window.</p>
            <script>
                try {{
                    const payload = {{ status: 'success', access_token: '{access_token}', timestamp: '{datetime.utcnow().isoformat()}' }};
                    if (window.opener && window.opener.postMessage) {{
                        window.opener.postMessage(payload, '*');
                    }}
                }} catch (e) {{ console.warn('postMessage failed', e); }}
                setTimeout(() => {{ window.close(); }}, 800);
            </script>
        </body>
    </html>
    """
    return HTMLResponse(content=html, status_code=200)


@app.get("/health")
async def health():
    """Health endpoint."""
    return {
        "status": "ok",
        "env_path": str(ENV_PATH),
        "has_access_token": bool(os.getenv("KITE_ACCESS_TOKEN")),
        "timestamp": datetime.utcnow().isoformat(),
    }


# ==============================================================
# 🔹 Startup & Watcher (Optional)
# ==============================================================

@app.on_event("startup")
async def on_startup():
    logger.info("🚀 [STARTUP] Token Refresher Service started successfully.")


@app.on_event("shutdown")
async def on_shutdown():
    logger.info("🧹 [SHUTDOWN] Token Refresher shutting down...")
