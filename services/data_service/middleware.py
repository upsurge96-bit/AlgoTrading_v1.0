"""
Error Handling Middleware
Centralized error handling for FastAPI application
"""

import logging
import traceback
from typing import Callable, Dict, Any
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from services.data_service.exceptions import (
    DataServiceException,
    ErrorCode,
    ConfigurationError,
    DatabaseError,
    AuthenticationError,
    WebSocketError,
    KafkaError,
    MinIOError,
    DataProcessingError,
    WorkerError,
    APIError,
    InvalidRequestError,
    ResourceNotFoundError,
    RateLimitExceededError
)

logger = logging.getLogger(__name__)


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to handle all exceptions and return standardized JSON responses
    
    Features:
    - Catches all DataServiceException subclasses
    - Logs errors with full context
    - Returns structured error responses
    - Handles unexpected exceptions gracefully
    """
    
    def __init__(self, app: ASGIApp):
        """Initialize middleware"""
        super().__init__(app)
        
        # Map exception types to HTTP status codes
        self.exception_status_map: Dict[type, int] = {
            InvalidRequestError: status.HTTP_400_BAD_REQUEST,
            ResourceNotFoundError: status.HTTP_404_NOT_FOUND,
            AuthenticationError: status.HTTP_401_UNAUTHORIZED,
            RateLimitExceededError: status.HTTP_429_TOO_MANY_REQUESTS,
            ConfigurationError: status.HTTP_500_INTERNAL_SERVER_ERROR,
            DatabaseError: status.HTTP_500_INTERNAL_SERVER_ERROR,
            WebSocketError: status.HTTP_503_SERVICE_UNAVAILABLE,
            KafkaError: status.HTTP_503_SERVICE_UNAVAILABLE,
            MinIOError: status.HTTP_503_SERVICE_UNAVAILABLE,
            DataProcessingError: status.HTTP_500_INTERNAL_SERVER_ERROR,
            WorkerError: status.HTTP_500_INTERNAL_SERVER_ERROR,
            APIError: status.HTTP_500_INTERNAL_SERVER_ERROR,
            DataServiceException: status.HTTP_500_INTERNAL_SERVER_ERROR,
        }
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and handle any exceptions
        
        Args:
            request: FastAPI request
            call_next: Next middleware/handler
            
        Returns:
            Response with error handling applied
        """
        try:
            # Process request
            response = await call_next(request)
            return response
            
        except DataServiceException as e:
            # Handle our custom exceptions
            return await self._handle_service_exception(request, e)
            
        except ValueError as e:
            # Handle validation errors
            return await self._handle_validation_error(request, e)
            
        except Exception as e:
            # Handle unexpected exceptions
            return await self._handle_unexpected_error(request, e)
    
    async def _handle_service_exception(
        self,
        request: Request,
        exc: DataServiceException
    ) -> JSONResponse:
        """
        Handle DataServiceException and subclasses
        
        Args:
            request: FastAPI request
            exc: Service exception
            
        Returns:
            JSONResponse with error details
        """
        # Get HTTP status code for exception type
        status_code = self._get_status_code(exc)
        
        # Log error with context
        log_context = {
            "path": request.url.path,
            "method": request.method,
            "error_code": exc.error_code.value,
            "error_name": exc.error_code.name,
        }
        
        if status_code >= 500:
            logger.error(
                f"Server error: {exc.message}",
                extra=log_context,
                exc_info=True
            )
        else:
            logger.warning(
                f"Client error: {exc.message}",
                extra=log_context
            )
        
        # Return structured error response
        return JSONResponse(
            status_code=status_code,
            content=exc.to_dict()
        )
    
    async def _handle_validation_error(
        self,
        request: Request,
        exc: ValueError
    ) -> JSONResponse:
        """
        Handle validation errors (converted to InvalidRequestError)
        
        Args:
            request: FastAPI request
            exc: ValueError
            
        Returns:
            JSONResponse with error details
        """
        # Convert to InvalidRequestError
        service_exc = InvalidRequestError(
            message=str(exc),
            details={"validation_error": str(exc)}
        )
        
        logger.warning(
            f"Validation error: {exc}",
            extra={
                "path": request.url.path,
                "method": request.method,
            }
        )
        
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=service_exc.to_dict()
        )
    
    async def _handle_unexpected_error(
        self,
        request: Request,
        exc: Exception
    ) -> JSONResponse:
        """
        Handle unexpected exceptions
        
        Args:
            request: FastAPI request
            exc: Unexpected exception
            
        Returns:
            JSONResponse with generic error
        """
        # Log full traceback
        logger.critical(
            f"Unexpected error: {exc}",
            extra={
                "path": request.url.path,
                "method": request.method,
                "exception_type": type(exc).__name__,
            },
            exc_info=True
        )
        
        # Create generic service exception
        service_exc = DataServiceException(
            message="An unexpected error occurred",
            error_code=ErrorCode.INTERNAL_ERROR,
            details={
                "exception_type": type(exc).__name__,
                "path": request.url.path,
            }
        )
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=service_exc.to_dict()
        )
    
    def _get_status_code(self, exc: DataServiceException) -> int:
        """
        Get HTTP status code for exception
        
        Args:
            exc: Service exception
            
        Returns:
            HTTP status code
        """
        # Check specific exception type
        for exc_type, status_code in self.exception_status_map.items():
            if isinstance(exc, exc_type):
                return status_code
        
        # Default to 500
        return status.HTTP_500_INTERNAL_SERVER_ERROR


class StructuredLogger:
    """
    Structured logging with context
    
    Adds request context to all log messages
    """
    
    def __init__(self, name: str):
        """Initialize logger"""
        self.logger = logging.getLogger(name)
    
    def _add_context(self, extra: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add common context to log extra
        
        Args:
            extra: Additional context
            
        Returns:
            Context with common fields
        """
        # You can add common fields here
        context = extra.copy() if extra else {}
        return context
    
    def debug(self, message: str, extra: Dict[str, Any] = None):
        """Log debug message"""
        self.logger.debug(message, extra=self._add_context(extra))
    
    def info(self, message: str, extra: Dict[str, Any] = None):
        """Log info message"""
        self.logger.info(message, extra=self._add_context(extra))
    
    def warning(self, message: str, extra: Dict[str, Any] = None):
        """Log warning message"""
        self.logger.warning(message, extra=self._add_context(extra))
    
    def error(self, message: str, extra: Dict[str, Any] = None, exc_info: bool = False):
        """Log error message"""
        self.logger.error(message, extra=self._add_context(extra), exc_info=exc_info)
    
    def critical(self, message: str, extra: Dict[str, Any] = None, exc_info: bool = False):
        """Log critical message"""
        self.logger.critical(message, extra=self._add_context(extra), exc_info=exc_info)


def get_logger(name: str) -> StructuredLogger:
    """
    Get structured logger
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        StructuredLogger instance
    """
    return StructuredLogger(name)


class CircuitBreaker:
    """
    Circuit breaker for external service calls
    
    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Too many failures, requests fail immediately
    - HALF_OPEN: Testing if service recovered
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception
    ):
        """
        Initialize circuit breaker
        
        Args:
            failure_threshold: Number of failures before opening
            recovery_timeout: Seconds to wait before attempting recovery
            expected_exception: Exception type to catch
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"
        
        self.logger = get_logger(__name__)
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker
        
        Args:
            func: Async function to call
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            Function result
            
        Raises:
            Exception: If circuit is OPEN or function fails
        """
        if self.state == "OPEN":
            if self._should_attempt_reset():
                self.state = "HALF_OPEN"
                self.logger.info("Circuit breaker entering HALF_OPEN state")
            else:
                raise Exception("Circuit breaker is OPEN")
        
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
            
        except self.expected_exception as e:
            self._on_failure()
            raise
    
    def _on_success(self):
        """Handle successful call"""
        if self.state == "HALF_OPEN":
            self.state = "CLOSED"
            self.logger.info("Circuit breaker CLOSED after successful call")
        
        self.failure_count = 0
        self.last_failure_time = None
    
    def _on_failure(self):
        """Handle failed call"""
        self.failure_count += 1
        self.last_failure_time = logging.time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            self.logger.error(
                f"Circuit breaker OPEN after {self.failure_count} failures"
            )
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset"""
        import time
        if self.last_failure_time is None:
            return True
        
        return (time.time() - self.last_failure_time) >= self.recovery_timeout
