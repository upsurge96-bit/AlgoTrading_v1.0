#!/usr/bin/env python3
"""
Main entry point for Auth Service.
This combined file serves both as the core application service 
and the FastAPI web service entry point.
"""

import sys
import os
import logging
import threading
from pathlib import Path

# Add parent directory to path to resolve imports
parent_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(parent_dir))

# Import core components
from core.application import Application
from core.token.manager import TokenManager, TokenRecord
from core.token.service import TokenService
from core.token.status import TokenStatus

# Make sure parent directory is in path for imports
sys.path.append(str(parent_dir))

# Import enhanced core logger - explicitly import needed modules first
import logging
import yaml  # Required for YAML config parsing

# Now import the core logger
from core.utils.logger import setup_logging, get_logger

# Import FastAPI components
from fastapi import FastAPI, Request, BackgroundTasks, Depends, HTTPException, Security
from fastapi.security import APIKeyHeader
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager

# Import middlewares and utilities
from api.middlewares import add_middlewares
from utils.security import secure_load_token, is_token_valid, get_token_expiry

# Configure logging
setup_logging(
    config_path="config/logging.yaml", 
    service_name="auth_service",
    environment=os.getenv("ENVIRONMENT", "development")
)
logger = get_logger("auth_service")

# Setup template and static folders
templates = Jinja2Templates(directory="templates")

# Define API key security for admin endpoints
API_KEY_NAME = "X-Admin-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "change-me-in-production")

# Create service instance
token_service = TokenService()

# ============================================================
# SECURITY FUNCTIONS
# ============================================================

async def get_api_key(api_key_header: str = Security(api_key_header)):
    """Validate API key for admin endpoints."""
    if not ADMIN_API_KEY or ADMIN_API_KEY == "change-me-in-production":
        logger.warning("Using default ADMIN_API_KEY! Set a strong key in production.")
    
    if api_key_header == ADMIN_API_KEY:
        return api_key_header
    else:
        raise HTTPException(
            status_code=403, 
            detail="Could not validate API key"
        )

# ============================================================
# CORE APPLICATION FUNCTIONS
# ============================================================

def start_core_application():
    """Start the core application service."""
    try:
        logger.info("Starting Auth Service Core Application")
        
        # Initialize application
        app = Application()
        app.initialize()
        
        # Start application
        app.start()
        
    except KeyboardInterrupt:
        logger.info("Auth Service Core Application stopped by user")
    except Exception as e:
        logger.error(f"Auth Service Core Application failed: {e}")
        sys.exit(1)

# ============================================================
# API APPLICATION SETUP
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Auth Service API")
    
    # Initialize and start token service in background
    service_thread = threading.Thread(target=token_service.start_background, daemon=True)
    service_thread.start()
    
    yield
    
    # Shutdown
    logger.info("Auth Service API stopped.")


# Create FastAPI app
app = FastAPI(
    title="Auth Service API", 
    description="Secure token generation and management service",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/admin/docs",  # Move docs to admin path
    redoc_url="/admin/redoc",  # Move redoc to admin path
)

# Add production middlewares
# In production, you should restrict CORS origins
allowed_origins = os.getenv("CORS_ORIGINS", "http://localhost,http://localhost:8018").split(",")
add_middlewares(app, origins=allowed_origins)

# Serve static files (css/js/images) from the service static/ folder - only if directory exists
static_dir = Path("static")
if static_dir.exists():
    app.mount("/static", StaticFiles(directory="static"), name="static")

# ============================================================
# ROUTES
# ============================================================

@app.get("/ui", include_in_schema=False)
async def ui_redirect():
    """Redirect /ui to the root UI page."""
    return RedirectResponse(url="/")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    token = secure_load_token()
    token_status = "valid" if token and is_token_valid(token) else "invalid"
    
    # Format the expires_at timestamp correctly for JavaScript Date object
    if token and token.get("expires_at"):
        from datetime import datetime
        try:
            # Convert Unix timestamp to ISO format for JavaScript
            timestamp = float(token["expires_at"])
            expires_at = datetime.fromtimestamp(timestamp).isoformat()
        except (ValueError, TypeError):
            # If already in string format or invalid, use as is
            expires_at = token.get("expires_at", "N/A")
    else:
        expires_at = "N/A"
    
    return templates.TemplateResponse("index.html", {
        "request": request, 
        "api_key": os.getenv("KITE_API_KEY", ""),
        "token_status": token_status,
        "expires_at": expires_at
    })

@app.get("/status")
async def status():
    """Get token status."""
    return token_service.token_manager.get_token_status()

@app.get("/refresh")
async def refresh_token():
    """Trigger manual token refresh."""
    return token_service.token_manager.trigger_refresh()

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return token_service.get_health_status()

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return token_service.get_metrics()

@app.get("/callback")
async def callback(request: Request, request_token: str = None, action: str = None, status: str = None, type: str = None):
    """
    Handle Zerodha callback after user authentication.
    
    This endpoint receives the request_token from Zerodha after successful login
    and exchanges it for an access token.
    """
    logger.info(f"Received callback: request_token={request_token}, action={action}, status={status}")
    
    if not request_token:
        logger.error("No request token provided in callback")
        raise HTTPException(status_code=400, detail="No request token provided")
        
    if status != "success":
        logger.error(f"Authentication failed: {status}")
        raise HTTPException(status_code=400, detail=f"Authentication failed: {status}")
    
    try:
        # Use token manager to create a token using the request token
        broker_id = "zerodha"  # Default broker
        token_manager = token_service.token_manager
        
        # Call refresh_token method with the request_token
        success = token_manager.refresh_token(broker_id, request_token)
        
        if success:
            # Redirect to home page with success message
            return RedirectResponse(url="/?status=success")
        else:
            # Redirect to home page with error message
            return RedirectResponse(url="/?status=error&message=Failed+to+exchange+token")
            
    except Exception as e:
        logger.exception(f"Error processing callback: {e}")
        # Redirect to home page with error message
        error_message = str(e).replace(" ", "+")
        return RedirectResponse(url=f"/?status=error&message={error_message}")

@app.get("/admin/token", dependencies=[Depends(get_api_key)])
async def get_token():
    """Admin endpoint to get token details."""
    # Get token details
    details = token_service.get_admin_token_details()
    
    # Transform response to format expected by data service
    tokens = details.get("tokens", [])
    if tokens:
        # Find zerodha token
        zerodha_token = next((t for t in tokens if t.get("broker_id") == "zerodha"), None)
        if zerodha_token:
            # Get actual token from token manager
            try:
                token_manager = token_service.token_manager
                token_record = token_manager.db.session.query(TokenRecord).filter_by(broker_id="zerodha").first()
                
                if token_record and token_record.access_token:
                    # Check if token is not expired
                    from datetime import datetime
                    if token_record.expiry_time > datetime.utcnow():
                        return {
                            "status": "success",
                            "data": {
                                "access_token": token_record.access_token,
                                "expires_at": token_record.expiry_time.isoformat(),
                                "broker": "zerodha"
                            }
                        }
            except Exception as e:
                logger.error(f"Error fetching token from database: {e}")
    
    # Return original details format for other uses
    return details

# Log app initialization
logger.info("Auth Service API initialized successfully")

# ============================================================
# MAIN ENTRY POINT
# ============================================================

def main():
    """
    Main entry point that can run either:
    1. Core application service
    2. FastAPI web service
    
    The mode is determined by the FASTAPI_MODE environment variable.
    """
    # Check if running in FastAPI mode
    if os.environ.get("FASTAPI_MODE", "true").lower() == "true":
        import uvicorn
        logger.info("Running in FastAPI mode")
        
        # Get port from environment or use default
        port = int(os.environ.get("PORT", 8018))
        
        # Run FastAPI app
        uvicorn.run(
            "main:app", 
            host="0.0.0.0", 
            port=port,
            log_level=os.environ.get("LOG_LEVEL", "info").lower()
        )
    else:
        # Run core application service
        logger.info("Running in core application mode")
        start_core_application()


if __name__ == "__main__":
    main()