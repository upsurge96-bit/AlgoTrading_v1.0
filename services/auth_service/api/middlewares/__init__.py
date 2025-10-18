"""
API Middlewares
-------------
Middleware initialization for the auth service API.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .rate_limit import RateLimitMiddleware
from .logging import RequestLoggingMiddleware
from .security import SecurityHeadersMiddleware

def add_middlewares(app: FastAPI, origins: list = None):
    """
    Add middlewares to the FastAPI application.
    
    Args:
        app: FastAPI application instance
        origins: List of allowed CORS origins
    """
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Add rate limiting middleware
    app.add_middleware(RateLimitMiddleware)
    
    # Add request logging middleware
    app.add_middleware(RequestLoggingMiddleware)
    
    # Add security headers middleware
    app.add_middleware(SecurityHeadersMiddleware)
    
    return app