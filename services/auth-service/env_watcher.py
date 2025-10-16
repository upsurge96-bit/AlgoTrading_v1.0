"""
token_refresher.py
--------------------------------------------------------
Flask microservice for Zerodha Kite API token management.

Features:
  ✅ Handle request_token → generate access_token
  ✅ Update `.env` safely (Docker or local)
  ✅ Log every update & reload confirmation
  ✅ Health check endpoint for monitoring

Usage:
    python token_refresher.py
    Visit → http://localhost:8018/update_token?request_token=<TOKEN>
--------------------------------------------------------
"""

import os
import logging
from pathlib import Path
from flask import Flask, request, jsonify
from dotenv import load_dotenv, set_key
from kiteconnect import KiteConnect
import sys, os
sys.path.append('/app') 
# =======================================================
# 🔹 Flask App & Logging Setup
# =======================================================
app = Flask(__name__)

logger = logging.getLogger("token_refresher")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger.info("🚀 Starting Token Refresher Service...")

# =======================================================
# 🔹 Load Environment (works in Docker + local)
# =======================================================
ENV_PATH = Path("/app/.env") if Path("/app/.env").exists() else Path(".env")

if not ENV_PATH.exists():
    raise FileNotFoundError(f"❌ .env file not found at {ENV_PATH}")

load_dotenv(ENV_PATH)
logger.info(f"✅ [ENV] Loaded environment variables from {ENV_PATH}")

KITE_API_KEY = os.getenv("KITE_API_KEY")
KITE_API_SECRET = os.getenv("KITE_API_SECRET")

if not KITE_API_KEY or not KITE_API_SECRET:
    logger.warning("⚠️ Missing Kite API credentials in .env")


# =======================================================
# 🔹 Routes
# =======================================================

@app.route("/update_token", methods=["GET"])
def update_token():
    """
    Endpoint: /update_token?request_token=<token>
    Generates new access/refresh tokens and saves them in .env.
    """
    request_token = request.args.get("request_token")
    if not request_token:
        logger.warning("⚠️ Missing request_token in query params")
        return jsonify({"error": "Missing request_token"}), 400

    logger.info(f"🔑 Received request_token: {request_token}")

    try:
        kite = KiteConnect(api_key=KITE_API_KEY)
        data = kite.generate_session(request_token, api_secret=KITE_API_SECRET)

        access_token = data["access_token"]
        refresh_token = data.get("refresh_token", "")

        # ✅ Update .env safely
        set_key(str(ENV_PATH), "KITE_REQUEST_TOKEN", request_token)
        set_key(str(ENV_PATH), "KITE_ACCESS_TOKEN", access_token)
        if refresh_token:
            set_key(str(ENV_PATH), "KITE_REFRESH_TOKEN", refresh_token)

        # Confirm reload
        load_dotenv(ENV_PATH, override=True)
        logger.info("🔐 [TOKEN] Access & Refresh tokens updated successfully.")
        logger.debug(f"[ACCESS_TOKEN] {access_token}")

        return jsonify({
            "status": "success",
            "message": "Tokens updated successfully",
            "access_token": access_token,
        }), 200

    except Exception as e:
        logger.exception("💥 Error during token refresh")
        return jsonify({"error": str(e)}), 500


@app.route("/", methods=["GET"])
def healthcheck():
    """Simple health check endpoint."""
    return jsonify({
        "status": "ok",
        "service": "token_refresher",
        "env": str(ENV_PATH),
    }), 200


# =======================================================
# 🔹 Entrypoint
# =======================================================
if __name__ == "__main__":
    host = "0.0.0.0" if os.getenv("DOCKER_ENV", "false").lower() == "true" else "localhost"
    logger.info(f"🌍 Running on http://{host}:8018")
    app.run(host=host, port=8018, debug=False)
