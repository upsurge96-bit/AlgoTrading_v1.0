"""
Token Error Classes
------------------
Defines exception classes for token refresh errors.
"""

class TokenRefreshError(Exception):
    """Base exception for token refresh errors."""
    pass

class AuthenticationError(TokenRefreshError):
    """Authentication failed with broker."""
    pass

class ConnectionError(TokenRefreshError):
    """Connection failed to broker API."""
    pass

class RateLimitError(TokenRefreshError):
    """Rate limit reached with broker API."""
    pass

class NetworkError(TokenRefreshError):
    """Network error connecting to broker API."""
    pass

class UnknownError(TokenRefreshError):
    """Unknown error during token refresh."""
    pass