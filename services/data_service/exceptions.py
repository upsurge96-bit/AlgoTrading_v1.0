"""
Custom Exceptions for Data Service
Production-ready exception hierarchy with proper error codes
"""

from typing import Optional, Dict, Any
from enum import Enum


class ErrorCode(str, Enum):
    """Error codes for better error categorization"""
    
    # Configuration errors (1000-1099)
    CONFIG_ERROR = "CONFIG_ERROR"
    INVALID_CONFIGURATION = "INVALID_CONFIGURATION"
    MISSING_CONFIGURATION = "MISSING_CONFIGURATION"
    
    # Database errors (2000-2099)
    DATABASE_ERROR = "DATABASE_ERROR"
    DATABASE_CONNECTION_ERROR = "DATABASE_CONNECTION_ERROR"
    DATABASE_QUERY_ERROR = "DATABASE_QUERY_ERROR"
    DATABASE_MIGRATION_ERROR = "DATABASE_MIGRATION_ERROR"
    
    # Authentication errors (3000-3099)
    AUTH_ERROR = "AUTH_ERROR"
    AUTH_TOKEN_ERROR = "AUTH_TOKEN_ERROR"
    AUTH_TOKEN_EXPIRED = "AUTH_TOKEN_EXPIRED"
    AUTH_SERVICE_UNAVAILABLE = "AUTH_SERVICE_UNAVAILABLE"
    
    # WebSocket errors (4000-4099)
    WEBSOCKET_ERROR = "WEBSOCKET_ERROR"
    WEBSOCKET_CONNECTION_ERROR = "WEBSOCKET_CONNECTION_ERROR"
    WEBSOCKET_DISCONNECTED = "WEBSOCKET_DISCONNECTED"
    WEBSOCKET_INVALID_MESSAGE = "WEBSOCKET_INVALID_MESSAGE"
    
    # Kafka errors (5000-5099)
    KAFKA_ERROR = "KAFKA_ERROR"
    KAFKA_CONNECTION_ERROR = "KAFKA_CONNECTION_ERROR"
    KAFKA_PUBLISH_ERROR = "KAFKA_PUBLISH_ERROR"
    
    # MinIO errors (6000-6099)
    MINIO_ERROR = "MINIO_ERROR"
    MINIO_CONNECTION_ERROR = "MINIO_CONNECTION_ERROR"
    MINIO_UPLOAD_ERROR = "MINIO_UPLOAD_ERROR"
    MINIO_BUCKET_ERROR = "MINIO_BUCKET_ERROR"
    
    # Data processing errors (7000-7099)
    DATA_PROCESSING_ERROR = "DATA_PROCESSING_ERROR"
    INVALID_DATA_FORMAT = "INVALID_DATA_FORMAT"
    DATA_VALIDATION_ERROR = "DATA_VALIDATION_ERROR"
    
    # API errors (8000-8099)
    API_ERROR = "API_ERROR"
    INVALID_REQUEST = "INVALID_REQUEST"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    
    # Worker errors (9000-9099)
    WORKER_ERROR = "WORKER_ERROR"
    WORKER_START_ERROR = "WORKER_START_ERROR"
    WORKER_STOP_ERROR = "WORKER_STOP_ERROR"
    
    # General errors
    INTERNAL_ERROR = "INTERNAL_ERROR"
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"


class DataServiceException(Exception):
    """Base exception for all data service errors"""
    
    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.INTERNAL_ERROR,
        details: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None
    ):
        """
        Initialize exception
        
        Args:
            message: Error message
            error_code: Error code for categorization
            details: Additional error details
            original_error: Original exception if wrapping another error
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.original_error = original_error
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses"""
        result = {
            "error": self.error_code.value,
            "message": self.message,
        }
        if self.details:
            result["details"] = self.details
        if self.original_error:
            result["original_error"] = str(self.original_error)
        return result
    
    def __str__(self) -> str:
        """String representation"""
        error_str = f"{self.error_code.value}: {self.message}"
        if self.details:
            error_str += f" | Details: {self.details}"
        return error_str


# Configuration Exceptions
class ConfigurationError(DataServiceException):
    """Configuration related errors"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code=ErrorCode.CONFIG_ERROR,
            details=details
        )


class InvalidConfigurationError(ConfigurationError):
    """Invalid configuration"""
    
    def __init__(self, message: str, config_key: str, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        details["config_key"] = config_key
        super().__init__(message=message, details=details)
        self.error_code = ErrorCode.INVALID_CONFIGURATION


class MissingConfigurationError(ConfigurationError):
    """Missing required configuration"""
    
    def __init__(self, config_key: str, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        details["config_key"] = config_key
        super().__init__(
            message=f"Missing required configuration: {config_key}",
            details=details
        )
        self.error_code = ErrorCode.MISSING_CONFIGURATION


# Database Exceptions
class DatabaseError(DataServiceException):
    """Database related errors"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None, original_error: Optional[Exception] = None):
        super().__init__(
            message=message,
            error_code=ErrorCode.DATABASE_ERROR,
            details=details,
            original_error=original_error
        )


class DatabaseConnectionError(DatabaseError):
    """Database connection error"""
    
    def __init__(self, message: str = "Failed to connect to database", details: Optional[Dict[str, Any]] = None, original_error: Optional[Exception] = None):
        super().__init__(message=message, details=details, original_error=original_error)
        self.error_code = ErrorCode.DATABASE_CONNECTION_ERROR


class DatabaseQueryError(DatabaseError):
    """Database query error"""
    
    def __init__(self, query: str, details: Optional[Dict[str, Any]] = None, original_error: Optional[Exception] = None):
        details = details or {}
        details["query"] = query
        super().__init__(
            message=f"Database query failed: {query}",
            details=details,
            original_error=original_error
        )
        self.error_code = ErrorCode.DATABASE_QUERY_ERROR


# Authentication Exceptions
class AuthenticationError(DataServiceException):
    """Authentication related errors"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None, original_error: Optional[Exception] = None):
        super().__init__(
            message=message,
            error_code=ErrorCode.AUTH_ERROR,
            details=details,
            original_error=original_error
        )


class TokenError(AuthenticationError):
    """Token related errors"""
    
    def __init__(self, message: str = "Token error", details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, details=details)
        self.error_code = ErrorCode.AUTH_TOKEN_ERROR


class TokenExpiredError(AuthenticationError):
    """Token expired error"""
    
    def __init__(self, message: str = "Access token has expired", details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, details=details)
        self.error_code = ErrorCode.AUTH_TOKEN_EXPIRED


# WebSocket Exceptions
class WebSocketError(DataServiceException):
    """WebSocket related errors"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None, original_error: Optional[Exception] = None):
        super().__init__(
            message=message,
            error_code=ErrorCode.WEBSOCKET_ERROR,
            details=details,
            original_error=original_error
        )


class WebSocketConnectionError(WebSocketError):
    """WebSocket connection error"""
    
    def __init__(self, message: str = "WebSocket connection failed", details: Optional[Dict[str, Any]] = None, original_error: Optional[Exception] = None):
        super().__init__(message=message, details=details, original_error=original_error)
        self.error_code = ErrorCode.WEBSOCKET_CONNECTION_ERROR


class WebSocketDisconnectedError(WebSocketError):
    """WebSocket disconnected"""
    
    def __init__(self, reason: str = "Connection closed", details: Optional[Dict[str, Any]] = None):
        details = details or {}
        details["reason"] = reason
        super().__init__(
            message=f"WebSocket disconnected: {reason}",
            details=details
        )
        self.error_code = ErrorCode.WEBSOCKET_DISCONNECTED


# Kafka Exceptions
class KafkaError(DataServiceException):
    """Kafka related errors"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None, original_error: Optional[Exception] = None):
        super().__init__(
            message=message,
            error_code=ErrorCode.KAFKA_ERROR,
            details=details,
            original_error=original_error
        )


class KafkaConnectionError(KafkaError):
    """Kafka connection error"""
    
    def __init__(self, brokers: str, details: Optional[Dict[str, Any]] = None, original_error: Optional[Exception] = None):
        details = details or {}
        details["brokers"] = brokers
        super().__init__(
            message=f"Failed to connect to Kafka: {brokers}",
            details=details,
            original_error=original_error
        )
        self.error_code = ErrorCode.KAFKA_CONNECTION_ERROR


# MinIO Exceptions
class MinIOError(DataServiceException):
    """MinIO related errors"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None, original_error: Optional[Exception] = None):
        super().__init__(
            message=message,
            error_code=ErrorCode.MINIO_ERROR,
            details=details,
            original_error=original_error
        )


class MinIOConnectionError(MinIOError):
    """MinIO connection error"""
    
    def __init__(self, endpoint: str, details: Optional[Dict[str, Any]] = None, original_error: Optional[Exception] = None):
        details = details or {}
        details["endpoint"] = endpoint
        super().__init__(
            message=f"Failed to connect to MinIO: {endpoint}",
            details=details,
            original_error=original_error
        )
        self.error_code = ErrorCode.MINIO_CONNECTION_ERROR


# Data Processing Exceptions
class DataProcessingError(DataServiceException):
    """Data processing errors"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None, original_error: Optional[Exception] = None):
        super().__init__(
            message=message,
            error_code=ErrorCode.DATA_PROCESSING_ERROR,
            details=details,
            original_error=original_error
        )


class InvalidDataFormatError(DataProcessingError):
    """Invalid data format"""
    
    def __init__(self, expected_format: str, received_format: str, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        details["expected"] = expected_format
        details["received"] = received_format
        super().__init__(
            message=f"Invalid data format. Expected: {expected_format}, Received: {received_format}",
            details=details
        )
        self.error_code = ErrorCode.INVALID_DATA_FORMAT


# Worker Exceptions
class WorkerError(DataServiceException):
    """Worker related errors"""
    
    def __init__(self, message: str, worker_name: str, details: Optional[Dict[str, Any]] = None, original_error: Optional[Exception] = None):
        details = details or {}
        details["worker"] = worker_name
        super().__init__(
            message=message,
            error_code=ErrorCode.WORKER_ERROR,
            details=details,
            original_error=original_error
        )


class WorkerStartError(WorkerError):
    """Worker start error"""
    
    def __init__(self, worker_name: str, details: Optional[Dict[str, Any]] = None, original_error: Optional[Exception] = None):
        super().__init__(
            message=f"Failed to start worker: {worker_name}",
            worker_name=worker_name,
            details=details,
            original_error=original_error
        )
        self.error_code = ErrorCode.WORKER_START_ERROR


# API Exceptions
class APIError(DataServiceException):
    """API related errors"""
    
    def __init__(self, message: str, status_code: int = 500, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        details["status_code"] = status_code
        super().__init__(
            message=message,
            error_code=ErrorCode.API_ERROR,
            details=details
        )
        self.status_code = status_code


class InvalidRequestError(APIError):
    """Invalid API request"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, status_code=400, details=details)
        self.error_code = ErrorCode.INVALID_REQUEST


class ResourceNotFoundError(APIError):
    """Resource not found"""
    
    def __init__(self, resource_type: str, resource_id: str, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        details["resource_type"] = resource_type
        details["resource_id"] = resource_id
        super().__init__(
            message=f"{resource_type} not found: {resource_id}",
            status_code=404,
            details=details
        )
        self.error_code = ErrorCode.RESOURCE_NOT_FOUND


class RateLimitExceededError(APIError):
    """Rate limit exceeded"""
    
    def __init__(self, limit: int, window: str, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        details["limit"] = limit
        details["window"] = window
        super().__init__(
            message=f"Rate limit exceeded: {limit} requests per {window}",
            status_code=429,
            details=details
        )
        self.error_code = ErrorCode.RATE_LIMIT_EXCEEDED
