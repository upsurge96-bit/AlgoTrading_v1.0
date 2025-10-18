"""
Rate Limiting Middleware
----------------------
Middleware for limiting request rates to prevent abuse.
"""

import time
from typing import Callable, Dict, Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware to prevent abuse.
    Uses a simple in-memory store for rate tracking.
    """
    
    def __init__(
        self,
        app: ASGIApp,
        rate_limit: int = 60,  # Requests per minute
        admin_rate_limit: int = 300,  # Higher limit for admin endpoints
        exclude_paths: Optional[list] = None
    ):
        super().__init__(app)
        self.rate_limit = rate_limit
        self.admin_rate_limit = admin_rate_limit
        self.exclude_paths = exclude_paths or ["/health", "/metrics"]
        # Simple in-memory store: {ip: [(timestamp, path), ...]}
        self._requests: Dict[str, list] = {}
        # Last cleanup time
        self._last_cleanup = time.time()
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip excluded paths
        if request.url.path in self.exclude_paths:
            return await call_next(request)
        
        # Clean up old entries periodically
        now = time.time()
        if now - self._last_cleanup > 60:  # Clean every minute
            self._cleanup_old_requests(now)
            self._last_cleanup = now
        
        # Get client IP
        ip = request.client.host if request.client else "unknown"
        
        # Choose rate limit based on path
        is_admin = request.url.path.startswith("/admin")
        limit = self.admin_rate_limit if is_admin else self.rate_limit
        
        # Check rate limit
        if not self._is_rate_limited(ip, request.url.path, limit, now):
            response = await call_next(request)
            return response
        else:
            return Response(
                content="Rate limit exceeded",
                status_code=429,
                headers={"Retry-After": "60"}
            )
    
    def _is_rate_limited(self, ip: str, path: str, limit: int, now: float) -> bool:
        """
        Check if the request exceeds the rate limit.
        
        Args:
            ip: Client IP address
            path: Request path
            limit: Rate limit to apply
            now: Current timestamp
        
        Returns:
            True if rate limited, False otherwise
        """
        # Initialize if needed
        if ip not in self._requests:
            self._requests[ip] = []
        
        # Add current request
        self._requests[ip].append((now, path))
        
        # Count requests in the last minute
        one_minute_ago = now - 60
        recent_requests = [
            req for req in self._requests[ip]
            if req[0] > one_minute_ago
        ]
        
        # Update stored requests with only recent ones
        self._requests[ip] = recent_requests
        
        # Check if exceeding limit
        return len(recent_requests) > limit
    
    def _cleanup_old_requests(self, now: float) -> None:
        """
        Remove request entries older than 1 minute.
        
        Args:
            now: Current timestamp
        """
        one_minute_ago = now - 60
        for ip in list(self._requests.keys()):
            self._requests[ip] = [
                req for req in self._requests[ip]
                if req[0] > one_minute_ago
            ]
            # Remove empty entries
            if not self._requests[ip]:
                del self._requests[ip]