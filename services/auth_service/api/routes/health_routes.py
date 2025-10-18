"""
Health Routes
------------
Health check and metrics endpoints.
"""

from api.routes import health_router
from core.token.service import TokenService

# Initialize services
token_service = TokenService()

@health_router.get("/health")
async def health_check():
    """Health check endpoint."""
    return token_service.get_health_status()

@health_router.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return token_service.get_metrics()