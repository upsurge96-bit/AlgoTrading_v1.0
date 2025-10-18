"""
Token Routes
-----------
Token management related routes.
"""

from fastapi import Request, Depends
from api.routes import token_router
from core.token.service import TokenService

# Initialize services
token_service = TokenService()

@token_router.get("/status")
async def status():
    """Get token status."""
    return token_service.token_manager.get_token_status()

@token_router.get("/refresh")
async def refresh_token():
    """Trigger manual token refresh."""
    return token_service.token_manager.trigger_refresh()