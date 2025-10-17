#!/usr/bin/env python3
"""
API Module
---------
FastAPI entry point for Auth Service that uses the modular structure.
"""

import os
import logging
from pathlib import Path

from fastapi import FastAPI, Request, BackgroundTasks, Depends, HTTPException, Security
from fastapi.security import APIKeyHeader
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager

# Import middlewares
from middlewares import add_middlewares

# Import core components
from lib.token.manager import TokenManager
from lib.token.service import TokenService
from lib.token.status import TokenStatus

# Import token security module
from token_security import secure_load_token, is_token_valid

# Configure logging
from core.utils.logger import get_logger
LOGGER = get_logger("auth_api")

# Setup template and static folders
templates = Jinja2Templates(directory="templates")

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
# APPLICATION SETUP
# ============================================================

# Create service instance
token_service = TokenService()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    LOGGER.info("Starting Auth Service API")
    
    # Initialize and start token service in background
    import threading
    service_thread = threading.Thread(target=token_service.start_background, daemon=True)
    service_thread.start()
    
    yield
    
    # Shutdown
    LOGGER.info("Auth Service API stopped.")


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

# Serve static files (css/js/images) from the service static/ folder
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
    expires_at = token.get("expires_at", "N/A") if token else "N/A"
    
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

@app.get("/admin/token", dependencies=[Depends(get_api_key)])
async def get_token():
    """Admin endpoint to get token details."""
    return token_service.get_admin_token_details()