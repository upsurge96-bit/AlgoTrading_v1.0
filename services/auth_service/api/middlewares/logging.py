"""
Request Logging Middleware
-----------------------
Middleware for logging requests and responses.
"""

import time
import logging
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger("api.request")

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Log details about requests and responses.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        # Get request details
        method = request.method
        url = str(request.url)
        client_ip = request.client.host if request.client else "unknown"
        
        # Process the request
        try:
            response = await call_next(request)
            
            # Calculate processing time
            process_time = time.time() - start_time
            
            # Log successful request
            logger.info(
                f"Request: {method} {url} {response.status_code} "
                f"- {process_time:.4f}s - {client_ip}"
            )
            
            return response
            
        except Exception as e:
            # Log failed request
            process_time = time.time() - start_time
            logger.error(
                f"Request failed: {method} {url} 500 "
                f"- {process_time:.4f}s - {client_ip} - {str(e)}"
            )
            raise