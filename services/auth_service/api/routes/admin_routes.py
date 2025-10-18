"""
Admin Routes
-----------
Admin-only routes for token management.
"""

from fastapi import Depends, Security, HTTPException
from fastapi.security import APIKeyHeader
import os
from api.routes import admin_router
from core.token.service import TokenService

# Define API key security for admin endpoints
API_KEY_NAME = "X-Admin-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "change-me-in-production")

# Initialize services
token_service = TokenService()

async def get_api_key(api_key_header: str = Security(api_key_header)):
    """Validate API key for admin endpoints."""
    if not ADMIN_API_KEY or ADMIN_API_KEY == "change-me-in-production":
        from core.utils.logger import get_logger
        logger = get_logger("admin_routes")
        logger.warning("Using default ADMIN_API_KEY! Set a strong key in production.")
    
    if api_key_header == ADMIN_API_KEY:
        return api_key_header
    else:
        raise HTTPException(
            status_code=403, 
            detail="Could not validate API key"
        )

@admin_router.get("/token", dependencies=[Depends(get_api_key)])
async def get_token():
    """Admin endpoint to get token details."""
    return token_service.get_admin_token_details()