"""
API Routes
---------
Route handlers for the auth service.
"""

from fastapi import APIRouter

# Create routers for different endpoints
auth_router = APIRouter(prefix="/auth", tags=["Authentication"])
token_router = APIRouter(prefix="/token", tags=["Token Management"])
admin_router = APIRouter(prefix="/admin", tags=["Admin"])
health_router = APIRouter(tags=["Health"])

# Import the route modules to register routes
from .auth_routes import *
from .token_routes import *
from .admin_routes import *
from .health_routes import *

# List of all routers to be included in the main app
routers = [
    auth_router,
    token_router,
    admin_router,
    health_router
]