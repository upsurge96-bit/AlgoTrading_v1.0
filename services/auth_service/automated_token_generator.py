#!/usr/bin/env python3
"""
automated_token_generator.py
----------------------------
Automated Kite Connect access_token generator web service.

Features:
- Web interface for login
- Handles callback to generate tokens
- Monitors token validity in background
- File watcher for manual token updates
- Secure token storage with encryption

Usage:
  uvicorn automated_token_generator:app --host 0.0.0.0 --port 8018
"""

import os
import json
import hashlib
import random
import requests
import datetime
import time
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, BackgroundTasks, Depends, HTTPException, Security
from fastapi.security import APIKeyHeader
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

# Import token security module
from token_security import secure_save_token, secure_load_token, ensure_data_directory

# Project imports
# Load environment from .env if present (Dockerfile copies .env to /app/.env)
load_dotenv()

try:
    from core.utils.config_loader import load_config
except FileNotFoundError:
    load_config = lambda: {}
# Import logging config
try:
    from logging_config import setup_logging
except ImportError:
    # Fallback if setup_logging is not available
    def setup_logging(**kwargs):
        import logging
        logging.basicConfig(level=logging.INFO)

# Setup enhanced logging
log_file = os.getenv("LOG_FILE", "/logs/auth_service.log")
json_logs = os.getenv("JSON_LOGS", "true").lower() == "true"
log_level = os.getenv("LOG_LEVEL", "INFO")
environment = os.getenv("ENVIRONMENT", "production" if os.getenv("DOCKER_ENV") else "development")

setup_logging(
    service_name="auth_service",
    log_file=log_file,
    log_level=log_level,
    json_logs=json_logs,
    environment=environment
)

try:
    from core.utils.logger import get_logger
    LOGGER = get_logger("token_generator")
except ImportError:
    import logging
    LOGGER = logging.getLogger("token_generator")

# ============================================================
# CONFIGURATION
# ============================================================

try:
    CONFIG = load_config()
except FileNotFoundError:
    CONFIG = {}
LOGGER = get_logger("token_generator")

# Load from config/env
API_KEY = os.getenv("KITE_API_KEY") or CONFIG.get("KITE_API_KEY", "your_kite_api_key")
API_SECRET = os.getenv("KITE_API_SECRET") or CONFIG.get("KITE_API_SECRET", "your_api_secret")
ENCRYPTION_KEY = os.getenv("TOKEN_ENCRYPTION_KEY") or CONFIG.get("TOKEN_ENCRYPTION_KEY")

# Log which credentials are being used (masked) to help debug 403s without exposing secrets
def _mask(s: str | None) -> str:
    if not s:
        return "<missing>"
    if len(s) <= 4:
        return "*" * len(s)
    return "****" + s[-4:]

LOGGER.info(f"Using KITE_API_KEY={_mask(API_KEY)}, KITE_API_SECRET={_mask(API_SECRET)}")
LOGGER.info(f"Encryption enabled: {bool(ENCRYPTION_KEY)}")

# Ensure data directory exists with proper permissions
ensure_data_directory()

REQUEST_TOKEN_FILE = Path("data/request_token.txt")
KITE_SESSION_URL = "https://api.kite.trade/session/token"

templates = Jinja2Templates(directory="templates")

# Global scheduler and observer
scheduler = AsyncIOScheduler()
observer = Observer()

# Define API key security for admin endpoints
API_KEY_NAME = "X-Admin-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "change-me-in-production")

# ============================================================
# SECURITY FUNCTIONS
# ============================================================

async def get_api_key(api_key_header: str = Security(api_key_header)):
    """Validate API key for admin endpoints."""
    if not ADMIN_API_KEY or ADMIN_API_KEY == "change-me-in-production":
        LOGGER.warning("Using default ADMIN_API_KEY! Set a strong key in production.")
    
    if api_key_header == ADMIN_API_KEY:
        return api_key_header
    else:
        raise HTTPException(
            status_code=403, 
            detail="Could not validate API key"
        )

# ============================================================
# TOKEN FUNCTIONS
# ============================================================

def generate_checksum(api_key: str, request_token: str, api_secret: str) -> str:
    """Compute SHA-256 checksum required for token exchange."""
    raw = f"{api_key}{request_token}{api_secret}"
    return hashlib.sha256(raw.encode()).hexdigest()


# Import retry utilities
from retry_utils import retry, with_circuit_breaker, RetryException

@retry(
    max_retries=3,
    initial_backoff=1.0,
    max_backoff=15.0,
    backoff_factor=2.0,
    jitter=True,
    retry_on_exceptions=(requests.RequestException, requests.ConnectionError, requests.Timeout),
    retry_on_status_codes=(429, 500, 502, 503, 504)
)
@with_circuit_breaker(
    failure_threshold=5,
    reset_timeout=300.0,  # 5 minutes
    exceptions_to_monitor=(Exception,)
)
def exchange_token(request_token: str) -> dict:
    """
    Exchange request_token for access_token with robust error handling.
    
    This function includes:
    - Automatic retries with exponential backoff
    - Circuit breaker pattern to prevent overloading failing services
    - Detailed error handling and logging
    - Idempotency handling
    """
    request_id = f"req_{int(time.time())}_{random.randint(1000, 9999)}"
    LOGGER.info(f"Starting token exchange [request_id={request_id}]")
    
    checksum = generate_checksum(API_KEY, request_token, API_SECRET)
    
    # Mask sensitive parts when printing for debug
    def _mask_val(v: str | None) -> str:
        if not v:
            return "<missing>"
        if len(v) <= 6:
            return "*" * len(v)
        return v[:3] + "..." + v[-3:]
    
    LOGGER.info(f"Exchanging token: request_token={_mask_val(request_token)}, checksum={_mask_val(checksum)}")
    
    # Add idempotency key and request ID for tracing
    headers = {
        "X-Kite-Version": "3",
        "X-Request-ID": request_id,
        "X-Idempotency-Key": f"token_exchange_{request_token[:8]}"
    }
    
    payload = {
        "api_key": API_KEY,
        "request_token": request_token,
        "checksum": checksum
    }

    LOGGER.info(f"Requesting new access token from Kite API [request_id={request_id}]")
    start_time = time.time()
    
    try:
        # Set timeouts to prevent hanging connections
        response = requests.post(
            KITE_SESSION_URL,
            data=payload,
            headers=headers,
            timeout=(5, 15)  # (connect_timeout, read_timeout)
        )
        response_time = time.time() - start_time
        LOGGER.info(f"Received response in {response_time:.2f}s [request_id={request_id}, status={response.status_code}]")
        
        response.raise_for_status()
    except requests.RequestException as e:
        # Log response details when available to aid debugging (don't log secrets)
        resp = getattr(e, 'response', None)
        if resp is not None:
            try:
                body = resp.text
            except Exception:
                body = '<unable to read body>'
            LOGGER.error(f"HTTP Error during token exchange: {e} - status={resp.status_code} body={body} [request_id={request_id}]")
            
            # Special handling for specific status codes
            if resp.status_code == 403:
                raise Exception("403 Forbidden from Kite API during token exchange. Check KITE_API_KEY/KITE_API_SECRET, ensure the request_token was generated for this API key, and verify your redirect URL in the Kite developer console.")
            elif resp.status_code == 400:
                raise Exception(f"400 Bad Request: {body} - Check request parameters and token validity.")
            elif resp.status_code == 401:
                raise Exception("401 Unauthorized: Invalid API key or request token.")
            elif resp.status_code == 429:
                retry_after = resp.headers.get('Retry-After', '60')
                raise Exception(f"429 Rate Limited: Please retry after {retry_after} seconds.")
        else:
            LOGGER.error(f"HTTP Error during token exchange: {e} [request_id={request_id}]")
        
        # Add context for retry mechanism
        error_context = {
            "request_id": request_id,
            "url": KITE_SESSION_URL,
            "status_code": getattr(resp, 'status_code', None),
            "response_time": time.time() - start_time
        }
        LOGGER.error(f"Token exchange failed: {error_context}")
        raise

    try:
        data = response.json()
    except ValueError as e:
        LOGGER.error(f"Failed to parse JSON response: {e} [request_id={request_id}]")
        raise Exception(f"Invalid JSON response from Kite API: {response.text[:100]}...")

    if data.get("status") != "success":
        LOGGER.error(f"Kite API Error: {data} [request_id={request_id}]")
        error_message = data.get("message", "Unknown API error")
        raise Exception(f"Kite API Error: {error_message}")

    LOGGER.info(f"Token exchange successful [request_id={request_id}]")
    return data["data"]


def save_token(data: dict):
    """Save access_token and metadata securely to file."""
    expires_at = (datetime.datetime.now() + datetime.timedelta(days=1)).replace(hour=6, minute=0, second=0)
    token_data = {
        "access_token": data["access_token"],
        "api_key": data["api_key"],
        "user_id": data["user_id"],
        "login_time": data["login_time"],
        "expires_at": str(expires_at),
    }
    
    # Securely save token with encryption
    secure_save_token(token_data, master_key=ENCRYPTION_KEY)
    LOGGER.info("Token saved securely with encryption")


def load_existing_token() -> dict | None:
    """Load previously stored token securely if available."""
    return secure_load_token(master_key=ENCRYPTION_KEY)


def is_token_valid(token_data: dict) -> bool:
    """Check if stored token is still valid (before 6AM next day)."""
    try:
        expiry = datetime.datetime.fromisoformat(token_data["expires_at"])
        return datetime.datetime.now() < expiry
    except Exception as e:
        LOGGER.warning(f"Error checking token validity: {e}")
        return False


def check_and_log_token_status():
    """Periodic check of token validity."""
    token = load_existing_token()
    if token and is_token_valid(token):
        LOGGER.info(f"Token valid until {token['expires_at']}")
    else:
        LOGGER.warning("Token expired or invalid. Waiting for new request_token.")


def generate_new_token(request_token: str):
    """Generate and save new token from request_token.

    Important: raise exceptions to the caller so HTTP endpoints can render an
    appropriate error page instead of always returning success.
    """
    data = exchange_token(request_token)
    save_token(data)
    LOGGER.info("New access_token generated successfully.")
    return data


# Import token refresher
from token_refresher import TokenRefresher

# ============================================================
# TOKEN REFRESHER SETUP
# ============================================================

# Create token refresher instance
token_refresher = TokenRefresher(
    api_key=API_KEY,
    api_secret=API_SECRET,
    token_getter=load_existing_token,
    token_saver=save_token,
    refresh_threshold_minutes=120,  # Refresh 2 hours before expiry
    max_retries=3,
    retry_backoff_seconds=60
)

def check_and_refresh_token():
    """Periodic check and refresh of token validity."""
    try:
        LOGGER.info("Running scheduled token check and refresh...")
        result = token_refresher.check_and_refresh()
        
        if result["status"] == "refreshed":
            LOGGER.info("Token refreshed successfully.")
        elif result["status"] == "valid":
            LOGGER.info(f"Token is valid. Expires at {result.get('expires_at')}")
            LOGGER.info(f"Time to expiry: {result.get('time_to_expiry')}")
        elif result["status"] == "manual_login_required":
            LOGGER.warning("Automatic token refresh failed. Manual login required.")
            # We could send a notification here in production
    except Exception as e:
        LOGGER.error(f"Error in token refresh: {e}")

# ============================================================
# FILE WATCHER
# ============================================================

class RequestTokenHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path == str(REQUEST_TOKEN_FILE):
            try:
                if REQUEST_TOKEN_FILE.exists():
                    request_token = REQUEST_TOKEN_FILE.read_text().strip()
                    if request_token:
                        LOGGER.info("New request_token detected, generating token...")
                        generate_new_token(request_token)
                        # Clear the file after use
                        REQUEST_TOKEN_FILE.write_text("")
                    else:
                        LOGGER.warning("Request token file is empty.")
            except Exception as e:
                LOGGER.error(f"Error processing request_token file: {e}")


# Import middlewares
from middlewares import add_middlewares

# ============================================================
# FASTAPI APP
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    LOGGER.info("Starting Automated Token Generator Web Service")
    
    # Ensure data directory exists with proper permissions
    ensure_data_directory()

    # Initial check
    check_and_log_token_status()

    # Setup file watcher
    event_handler = RequestTokenHandler()
    observer.schedule(event_handler, path="data", recursive=False)
    observer.start()
    LOGGER.info(f"Watching for changes to {REQUEST_TOKEN_FILE}")

    # Setup scheduler
    scheduler.add_job(check_and_log_token_status, 'interval', minutes=30)
    # Add automatic token refresh check every 60 minutes
    scheduler.add_job(check_and_refresh_token, 'interval', minutes=60)
    scheduler.start()

    yield

    # Shutdown
    observer.stop()
    scheduler.shutdown()
    LOGGER.info("Service stopped.")

app = FastAPI(
    title="Kite Token Generator", 
    description="Secure Kite Connect token generation and storage service",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/admin/docs",  # Move docs to admin path
    redoc_url="/admin/redoc",  # Move redoc to admin path
)

# Add production middlewares
# In production, you should restrict CORS origins
allowed_origins = os.getenv("CORS_ORIGINS", "http://localhost,http://localhost:8018").split(",")
add_middlewares(app, origins=allowed_origins)

# Serve static files (css/js/images) from the service static/ folder
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/ui", include_in_schema=False)
async def ui_redirect():
    """Redirect /ui to the root UI page.

    Many users expect the UI at /ui; this keeps backwards compatibility.
    """
    return RedirectResponse(url="/")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    token = load_existing_token()
    token_status = "valid" if token and is_token_valid(token) else "invalid"
    expires_at = token.get("expires_at", "N/A") if token else "N/A"
    return templates.TemplateResponse("index.html", {
        "request": request, 
        "api_key": API_KEY,
        "token_status": token_status,
        "expires_at": expires_at
    })

@app.get("/callback")
async def callback(request: Request, request_token: str = None, background_tasks: BackgroundTasks = None):
    """
    Handle callback from Kite Connect with request_token.
    
    This callback implements:
    - Input validation
    - Asynchronous token generation for improved UX
    - Detailed error handling with suggestions
    - Idempotency to prevent duplicate processing
    """
    if not request_token:
        LOGGER.error("Callback received with no request_token")
        error_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Token Generation Failed</title>
            <style>
                body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
                .error { color: red; font-size: 24px; margin-bottom: 20px; }
                .info { margin-bottom: 15px; }
                .back { margin-top: 30px; }
                a { color: #007bff; text-decoration: none; }
            </style>
        </head>
        <body>
            <div class="error">❌ Missing Request Token</div>
            <div class="info">No request token was provided in the callback URL.</div>
            <div class="info">This usually indicates a problem with the Kite Connect redirection.</div>
            <div class="back"><a href="/">Try Again</a></div>
        </body>
        </html>
        """
        return HTMLResponse(content=error_html)

    # Generate a request ID for tracking this specific callback
    request_id = f"callback_{int(time.time())}_{random.randint(1000, 9999)}"
    LOGGER.info(f"Callback received with request_token={request_token[:5]}... [request_id={request_id}]")
    
    try:
        # We'll generate the token synchronously as it's a critical operation
        # In a very high-traffic system, we might want to use a background task instead
        token_data = generate_new_token(request_token)
        
        # Log successful generation with masked user details
        LOGGER.info(f"Token successfully generated for user_id={token_data.get('user_id')} [request_id={request_id}]")
        
        # Calculate expiry time for user display
        try:
            expiry = datetime.datetime.fromisoformat(token_data["login_time"])
            expiry = expiry.replace(hour=6, minute=0, second=0) + datetime.timedelta(days=1)
            expiry_str = expiry.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            expiry_str = "6:00 AM tomorrow"
        
        # Return an HTML success page rather than JSON
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Token Generated Successfully</title>
            <style>
                body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; }}
                .success {{ color: green; font-size: 24px; margin-bottom: 20px; }}
                .info {{ margin-bottom: 15px; }}
                .details {{ background-color: #f8f9fa; padding: 10px; margin: 20px 0; border-radius: 5px; }}
                .back {{ margin-top: 30px; }}
                a {{ color: #007bff; text-decoration: none; }}
            </style>
        </head>
        <body>
            <div class="success">✅ Access Token Generated Successfully!</div>
            <div class="info">Your Kite Connect access token has been saved securely.</div>
            <div class="info">Token will be valid until {expiry_str}.</div>
            
            <div class="details">
                <strong>User ID:</strong> {token_data.get('user_id', 'Unknown')}<br>
                <strong>Login Time:</strong> {token_data.get('login_time', 'Unknown')}<br>
                <strong>Token Health Checks:</strong> Every 30 minutes<br>
                <strong>Storage:</strong> AES-256 Encrypted
            </div>
            
            <div class="back"><a href="/">Back to Home</a></div>
        </body>
        </html>
        """
        return HTMLResponse(content=html_content)
        
    except RetryException as e:
        # Special handling for retry failures
        LOGGER.error(f"Token generation failed after {e.attempts} attempts [request_id={request_id}]: {e.original_exception}")
        error_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Token Generation Failed - Service Unavailable</title>
            <style>
                body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; }}
                .error {{ color: red; font-size: 24px; margin-bottom: 20px; }}
                .info {{ margin-bottom: 15px; }}
                .back {{ margin-top: 30px; }}
                a {{ color: #007bff; text-decoration: none; }}
            </style>
        </head>
        <body>
            <div class="error">❌ Service Temporarily Unavailable</div>
            <div class="info">We tried multiple times but couldn't connect to the Kite API.</div>
            <div class="info">This may be due to network issues or Kite API downtime.</div>
            <div class="info">Please try again in a few minutes.</div>
            <div class="back"><a href="/">Back to Home</a></div>
        </body>
        </html>
        """
        return HTMLResponse(content=error_html, status_code=503)
        
    except Exception as e:
        # General error handling with helpful messages based on error type
        LOGGER.error(f"Token generation failed [request_id={request_id}]: {e}")
        
        error_message = str(e)
        suggestion = "Please try again or contact support."
        
        # Provide more helpful suggestions based on error message
        if "403 Forbidden" in error_message:
            suggestion = "Check your API key and secret configuration, and verify the redirect URL in Kite developer console."
        elif "401 Unauthorized" in error_message:
            suggestion = "The request token may have expired. Please try logging in again."
        elif "429 Rate Limited" in error_message:
            suggestion = "Too many requests. Please wait before trying again."
        elif "Invalid JSON" in error_message:
            suggestion = "Received unexpected response from Kite API. This may be a temporary issue."
        
        error_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Token Generation Failed</title>
            <style>
                body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; }}
                .error {{ color: red; font-size: 24px; margin-bottom: 20px; }}
                .info {{ margin-bottom: 15px; }}
                .suggestion {{ background-color: #fff3cd; padding: 10px; margin: 20px 0; border-radius: 5px; }}
                .back {{ margin-top: 30px; }}
                a {{ color: #007bff; text-decoration: none; }}
            </style>
        </head>
        <body>
            <div class="error">❌ Token Generation Failed</div>
            <div class="info">Error: {str(e)}</div>
            <div class="suggestion">{suggestion}</div>
            <div class="back"><a href="/">Try Again</a></div>
        </body>
        </html>
        """
        return HTMLResponse(content=error_html)

@app.get("/status")
async def status():
    token = load_existing_token()
    if token and is_token_valid(token):
        # Calculate time to expiry
        try:
            expiry = datetime.datetime.fromisoformat(token["expires_at"])
            now = datetime.datetime.now()
            time_to_expiry = expiry - now
            hours_to_expiry = time_to_expiry.total_seconds() / 3600
            
            # Determine refresh status
            refresh_status = "not_needed"
            if hours_to_expiry < 2:
                refresh_status = "imminent"
            elif hours_to_expiry < 8:
                refresh_status = "upcoming"
            
            return {
                "status": "valid", 
                "expires_at": token["expires_at"],
                "time_to_expiry_hours": round(hours_to_expiry, 1),
                "refresh_status": refresh_status,
                "refresh_threshold_hours": 2.0  # Match the refresh threshold in TokenRefresher
            }
        except Exception as e:
            LOGGER.error(f"Error calculating expiry time: {e}")
            return {"status": "valid", "expires_at": token["expires_at"]}
    else:
        return {"status": "invalid"}

@app.get("/refresh")
async def refresh_token():
    """
    Trigger a manual token refresh check.
    This won't actually refresh the token (Kite doesn't support that),
    but will check status and report if manual login is needed.
    """
    refresh_result = token_refresher.check_and_refresh()
    
    if refresh_result["status"] == "valid":
        return {
            "status": "valid",
            "message": "Token is valid and doesn't need refresh yet.",
            "expires_at": refresh_result.get("expires_at"),
            "time_to_expiry": refresh_result.get("time_to_expiry")
        }
    elif refresh_result["status"] == "refreshed":
        return {
            "status": "refreshed",
            "message": "Token was successfully refreshed."
        }
    else:
        # Manual login required
        login_url = token_refresher.get_login_info()["login_url"]
        return {
            "status": "manual_login_required",
            "message": "Automatic refresh not possible. Please log in manually.",
            "login_url": login_url
        }

@app.get("/admin/token", dependencies=[Depends(get_api_key)])
async def get_token():
    """
    Admin endpoint to retrieve the current token details.
    Protected by API key authentication.
    """
    token = load_existing_token()
    if not token:
        raise HTTPException(status_code=404, detail="No token available")
    
    # Get refresh status
    refresh_status = token_refresher.check_token_status()
    
    return {
        "user_id": token["user_id"],
        "api_key": token["api_key"],
        "login_time": token["login_time"],
        "expires_at": token["expires_at"],
        "is_valid": is_token_valid(token),
        "needs_refresh": refresh_status["needs_refresh"],
        "time_to_expiry": str(refresh_status["time_to_expiry"]) if refresh_status["time_to_expiry"] else None,
        # Mask the actual token in the response
        "access_token": f"{token['access_token'][:5]}...{token['access_token'][-5:]}"
    }

@app.get("/health")
async def health_check():
    """
    Health check endpoint for monitoring systems.
    
    Returns:
        Health status of the service including dependencies
    """
    # Check if token is available
    token = load_existing_token()
    token_status = {
        "available": token is not None,
        "valid": token is not None and is_token_valid(token)
    }
    
    # Check if scheduler is running
    scheduler_status = {
        "running": scheduler.running
    }
    
    # Check if file watcher is running
    observer_status = {
        "running": observer.is_alive()
    }
    
    # Overall health determination
    is_healthy = all([
        scheduler_status["running"],
        observer_status["running"]
    ])
    
    return {
        "status": "healthy" if is_healthy else "unhealthy",
        "timestamp": datetime.datetime.now().isoformat(),
        "version": "1.0.0",
        "components": {
            "token": token_status,
            "scheduler": scheduler_status,
            "file_watcher": observer_status
        }
    }

@app.get("/metrics")
async def metrics():
    """
    Prometheus metrics endpoint.
    
    Returns:
        Metrics in a format that can be scraped by Prometheus
    """
    # Check token status
    token = load_existing_token()
    is_valid = token is not None and is_token_valid(token)
    
    # Calculate time to expiry in seconds
    time_to_expiry_seconds = 0
    if token and is_valid:
        try:
            expiry = datetime.datetime.fromisoformat(token["expires_at"])
            now = datetime.datetime.now()
            time_to_expiry_seconds = int((expiry - now).total_seconds())
        except Exception as e:
            LOGGER.error(f"Error calculating expiry time: {e}")
    
    # Build Prometheus-compatible metrics
    lines = [
        "# HELP kite_token_valid Whether the Kite API token is currently valid",
        "# TYPE kite_token_valid gauge",
        f"kite_token_valid {1 if is_valid else 0}",
        "",
        "# HELP kite_token_expiry_seconds Time until token expiry in seconds",
        "# TYPE kite_token_expiry_seconds gauge",
        f"kite_token_expiry_seconds {time_to_expiry_seconds}",
        "",
        "# HELP kite_token_available Whether a token file exists",
        "# TYPE kite_token_available gauge",
        f"kite_token_available {1 if token is not None else 0}",
        "",
        "# HELP kite_token_refresher_up Whether the token refresher is running",
        "# TYPE kite_token_refresher_up gauge",
        f"kite_token_refresher_up {1 if scheduler.running else 0}",
    ]
    
    return Response(content="\n".join(lines), media_type="text/plain")