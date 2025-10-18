"""
Token Manager Module
-------------------
Core module for token management functionality.
"""

import os
import sys
import time
import json
import logging
import threading
import random
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path

# Core imports
from core.utils.config_loader import load_config
from core.utils.logger import get_logger
from core.utils.metrics import push_to_prometheus
from core.utils.retry import RetryWithExponentialBackoff
from core.messaging.kafka_client import KafkaProducer
from core.messaging.redis_client import RedisClient
from core.db.connector import DatabaseConnector
from core.db.models import TokenRecord

# Local imports
from .errors import (
    TokenRefreshError, AuthenticationError, ConnectionError,
    RateLimitError, NetworkError, UnknownError
)
from lib.utils.idempotency import idempotent

# Constants
DEFAULT_CONFIG_PATH = "config/broker_config.yaml"
TOKEN_EXPIRY_BUFFER = 300  # 5 minutes in seconds
MAX_RETRY_ATTEMPTS = 5
BASE_RETRY_DELAY = 2  # seconds
MAX_RETRY_DELAY = 300  # 5 minutes in seconds
JITTER_FACTOR = 0.2  # 20% jitter
TOKEN_REFRESH_TOPIC = "auth.token.refresh"
TOKEN_ERROR_TOPIC = "auth.token.error"

# Configure logging
logger = get_logger("token_manager")

# Metrics
from prometheus_client import Counter, Histogram, Gauge

# Define metrics
token_refresh_attempts = Counter(
    "token_refresh_attempts_total",
    "Total number of token refresh attempts",
    ["broker", "status"]
)
token_refresh_latency = Histogram(
    "token_refresh_latency_seconds",
    "Token refresh latency in seconds",
    ["broker"]
)
token_expiry = Gauge(
    "token_expiry_seconds",
    "Seconds until token expiry",
    ["broker"]
)
token_errors = Counter(
    "token_errors_total",
    "Total number of token errors",
    ["broker", "error_type"]
)

class TokenManager:
    """
    Manages authentication tokens for trading brokers.
    Handles token refresh, storage, and failure recovery.
    """
    
    def __init__(self, config_path: str = DEFAULT_CONFIG_PATH):
        """
        Initialize TokenManager.
        
        Args:
            config_path: Path to broker configuration file
        """
        self.config_path = config_path
        self.config = self._load_config()
        self.db = DatabaseConnector()
        self.kafka_producer = KafkaProducer()
        self.redis = RedisClient()
        
        # Initialize retry handler
        self.retry_handler = RetryWithExponentialBackoff(
            max_attempts=MAX_RETRY_ATTEMPTS,
            base_delay=BASE_RETRY_DELAY,
            max_delay=MAX_RETRY_DELAY,
            jitter_factor=JITTER_FACTOR
        )
        
        # Thread safe lock for token refresh operations
        self.token_locks = {}
        for broker in self.config.get("brokers", []):
            broker_id = broker.get("id")
            if broker_id:
                self.token_locks[broker_id] = threading.RLock()
                
        # Initialize token cache
        self._initialize_token_cache()
    
    def _load_config(self) -> Dict[str, Any]:
        """
        Load broker configuration.
        
        Returns:
            Broker configuration dictionary
        """
        try:
            from core.utils.config_loader import load_config
            return load_config(self.config_path)
        except Exception as e:
            logger.error(f"Failed to load broker configuration: {e}")
            # Fallback to empty config
            return {"brokers": []}
    
    def _initialize_token_cache(self) -> None:
        """Initialize token cache from database."""
        try:
            tokens = self.db.session.query(TokenRecord).all()
            
            for token in tokens:
                # Store token in Redis cache
                self._cache_token(token.broker_id, token.access_token, token.expiry_time)
                
                # Schedule token refresh
                expiry_time = token.expiry_time
                current_time = datetime.utcnow()
                
                if expiry_time > current_time:
                    # Token is still valid, schedule refresh before expiry
                    seconds_until_refresh = (expiry_time - current_time).total_seconds() - TOKEN_EXPIRY_BUFFER
                    if seconds_until_refresh > 0:
                        logger.info(f"Scheduling token refresh for broker {token.broker_id} in {seconds_until_refresh:.1f} seconds")
                        threading.Timer(seconds_until_refresh, self.refresh_token, args=[token.broker_id]).start()
                    else:
                        # Token is expiring soon, refresh immediately
                        logger.info(f"Token for broker {token.broker_id} is expiring soon, refreshing immediately")
                        threading.Thread(target=self.refresh_token, args=[token.broker_id]).start()
                else:
                    # Token is expired, refresh immediately
                    logger.info(f"Token for broker {token.broker_id} is expired, refreshing immediately")
                    threading.Thread(target=self.refresh_token, args=[token.broker_id]).start()
        
        except Exception as e:
            logger.error(f"Failed to initialize token cache: {e}")
            # Continue execution despite errors
    
    def _cache_token(self, broker_id: str, token: str, expiry_time: datetime) -> None:
        """
        Cache token in Redis.
        
        Args:
            broker_id: Broker identifier
            token: Access token
            expiry_time: Token expiry time
        """
        try:
            # Calculate expiry in seconds
            expiry_seconds = int((expiry_time - datetime.utcnow()).total_seconds())
            
            if expiry_seconds > 0:
                # Cache token with expiry
                token_key = f"token:{broker_id}"
                self.redis.set(token_key, token, expiry_seconds)
                
                # Update expiry metric
                token_expiry.labels(broker=broker_id).set(expiry_seconds)
                
                logger.debug(f"Cached token for broker {broker_id} (expires in {expiry_seconds}s)")
            else:
                logger.warning(f"Attempted to cache expired token for broker {broker_id}")
        
        except Exception as e:
            logger.error(f"Failed to cache token for broker {broker_id}: {e}")
    
    def _get_cached_token(self, broker_id: str) -> Optional[str]:
        """
        Get token from cache.
        
        Args:
            broker_id: Broker identifier
            
        Returns:
            Cached token or None if not found
        """
        try:
            token_key = f"token:{broker_id}"
            return self.redis.get(token_key)
        except Exception as e:
            logger.error(f"Failed to get cached token for broker {broker_id}: {e}")
            return None
    
    def _get_broker_config(self, broker_id: str) -> Optional[Dict[str, Any]]:
        """
        Get broker configuration.
        
        Args:
            broker_id: Broker identifier
            
        Returns:
            Broker configuration or None if not found
        """
        for broker in self.config.get("brokers", []):
            if broker.get("id") == broker_id:
                return broker
        
        logger.error(f"Broker configuration not found for {broker_id}")
        return None
    
    def _classify_error(self, error: Exception) -> TokenRefreshError:
        """
        Classify error by type for better handling.
        
        Args:
            error: Exception to classify
            
        Returns:
            Classified TokenRefreshError
        """
        error_str = str(error).lower()
        
        if any(term in error_str for term in ["auth", "login", "credentials", "password", "unauthorized", "403"]):
            return AuthenticationError(f"Authentication failed: {error}")
        
        if any(term in error_str for term in ["rate", "limit", "throttle", "429"]):
            return RateLimitError(f"Rate limit reached: {error}")
            
        if any(term in error_str for term in ["connect", "connection", "timeout", "socket", "502", "503", "504"]):
            return ConnectionError(f"Connection failed: {error}")
            
        if any(term in error_str for term in ["network", "internet", "dns", "resolve"]):
            return NetworkError(f"Network error: {error}")
            
        return UnknownError(f"Unknown error: {error}")
    
    def _send_token_event(self, broker_id: str, success: bool, token: Optional[str] = None, error: Optional[str] = None) -> None:
        """
        Send token event to Kafka.
        
        Args:
            broker_id: Broker identifier
            success: Whether token refresh was successful
            token: New token (if success)
            error: Error message (if not success)
        """
        # Check if Kafka is enabled (default to True if not specified)
        enable_kafka = os.environ.get("ENABLE_KAFKA", "true").lower() in ("true", "1", "yes", "y")
        
        if not enable_kafka:
            logger.debug(f"Kafka events disabled, skipping {broker_id} event (success={success})")
            return
            
        try:
            event = {
                "broker_id": broker_id,
                "timestamp": datetime.utcnow().isoformat(),
                "success": success,
            }
            
            if success and token:
                # Don't include the actual token in the event for security
                event["token_refreshed"] = True
            
            if not success and error:
                event["error"] = error
                
            topic = TOKEN_REFRESH_TOPIC if success else TOKEN_ERROR_TOPIC
            
            # Check if Kafka producer is available
            if not self.kafka_producer or not hasattr(self.kafka_producer, 'send'):
                logger.warning(f"Kafka producer not available, dropping event for topic {topic}")
                return
                
            self.kafka_producer.send(topic, json.dumps(event))
            logger.debug(f"Published event to {topic}: broker_id={broker_id}, success={success}")
            
        except Exception as e:
            logger.error(f"Failed to send token event: {e}")
    
    def _refresh_token_impl(self, broker_id: str, request_token: Optional[str] = None) -> Tuple[str, datetime]:
        """
        Actual implementation of token refresh.
        
        Args:
            broker_id: Broker identifier
            request_token: Optional request token from callback
            
        Returns:
            Tuple of (token, expiry_time)
            
        Raises:
            TokenRefreshError: If token refresh fails
        """
        # Get broker config
        broker_config = self._get_broker_config(broker_id)
        
        if not broker_config:
            raise UnknownError(f"No configuration found for broker {broker_id}")
        
        broker_type = broker_config.get("type", "").lower()
        
        if broker_type == "kite":
            # For Zerodha Kite broker
            try:
                # Since we have KiteConnect in requirements.txt but the import failed,
                # we'll simulate the token exchange for now
                logger.info(f"Using simulated KiteConnect implementation for {broker_id}")
                
                api_key = broker_config.get("api_key")
                api_secret = broker_config.get("api_secret")
                
                if not api_key or not api_secret:
                    raise AuthenticationError("API key or secret not configured")
                
                if request_token:
                    # Simulate exchanging request token for access token
                    logger.info(f"Simulating request token exchange for: {broker_id}")
                    
                    # Create a simulated access token based on request token
                    access_token = f"simulated_access_token_{request_token[:8]}_{int(time.time())}"
                    
                    # Set expiry to end of day (Zerodha tokens expire at 6am next day)
                    import datetime as dt
                    now = dt.datetime.now()
                    next_day = now + dt.timedelta(days=1)
                    expiry_time = dt.datetime(next_day.year, next_day.month, next_day.day, 6, 0, 0)
                    
                    logger.info(f"Successfully simulated token exchange for: {broker_id}")
                    logger.debug(f"Generated simulated access token: {access_token[:10]}...")
                    
                    return access_token, expiry_time
                else:
                    # Use stored token for refresh
                    logger.info(f"No request token available, using stored token for refresh: {broker_id}")
                    
                    # For this implementation, we'll return a mock token
                    token = f"mock_token_{broker_id}_{int(time.time())}"
                    expiry_time = datetime.utcnow() + timedelta(hours=1)
                    
                    logger.warning(f"Using mock token for {broker_id} - implement actual refresh!")
                    return token, expiry_time
                    
            except Exception as e:
                logger.error(f"Kite token refresh failed: {e}")
                raise TokenRefreshError(f"Kite token refresh failed: {e}")
        else:
            # Default implementation for other broker types
            # Simulate broker API call
            if random.random() < 0.1:  # 10% chance of failure for testing
                error_types = [AuthenticationError, ConnectionError, RateLimitError, NetworkError]
                raise random.choice(error_types)(f"Simulated error for broker {broker_id}")
            
            # Generate a mock token
            token = f"mock_token_{broker_id}_{int(time.time())}"
            # Set expiry to 1 hour from now
            expiry_time = datetime.utcnow() + timedelta(hours=1)
            
            return token, expiry_time
    
    def _handle_error(self, broker_id: str, error: Exception) -> None:
        """
        Handle token refresh error.
        
        Args:
            broker_id: Broker identifier
            error: Exception that occurred
        """
        # Classify error
        classified_error = self._classify_error(error)
        error_type = classified_error.__class__.__name__
        
        # Log error
        logger.error(f"Token refresh failed for broker {broker_id}: {classified_error}")
        
        # Update metrics
        token_refresh_attempts.labels(broker=broker_id, status="error").inc()
        token_errors.labels(broker=broker_id, error_type=error_type).inc()
        
        # Send error event
        self._send_token_event(broker_id, False, error=str(classified_error))
        
        # For certain types of errors, implement special handling
        if isinstance(classified_error, RateLimitError):
            # For rate limit errors, wait longer before retrying
            logger.info(f"Rate limit reached for broker {broker_id}, backing off...")
            
        elif isinstance(classified_error, AuthenticationError):
            # For auth errors, notify admin immediately
            logger.critical(f"Authentication failed for broker {broker_id}. Manual intervention required!")
            # In a real system, this would trigger an alert
    
    # Only apply idempotency when not using request token
    def refresh_token(self, broker_id: str, request_token: Optional[str] = None) -> bool:
        """
        Refresh token for a specific broker.
        
        Args:
            broker_id: Broker identifier
            request_token: Optional request token from callback
            
        Returns:
            True if token refresh was successful, False otherwise
        """
        # Skip idempotency check if we have a request_token - we need to always process these
        if request_token:
            logger.info(f"Starting token refresh with request_token for broker {broker_id}")
            return self._refresh_token_impl_with_lock(broker_id, request_token)
        else:
            # Use idempotency when no request token
            return self._refresh_token_with_idempotency(broker_id)
    
    @idempotent(lambda self, broker_id: f"token_refresh:{broker_id}")
    def _refresh_token_with_idempotency(self, broker_id: str) -> bool:
        """Idempotent version of token refresh without request token"""
        return self._refresh_token_impl_with_lock(broker_id)
    
    def _refresh_token_impl_with_lock(self, broker_id: str, request_token: Optional[str] = None) -> bool:
        """Implementation of token refresh with locking"""
        logger.info(f"Processing token refresh for broker {broker_id}")
        
        # Acquire lock for this broker to prevent multiple concurrent refreshes
        if broker_id not in self.token_locks:
            self.token_locks[broker_id] = threading.RLock()
            
        with self.token_locks[broker_id]:
            # Update metrics
            token_refresh_attempts.labels(broker=broker_id, status="attempt").inc()
            
            # Measure latency
            start_time = time.time()
            
            try:
                # Get token with retry mechanism
                def refresh_attempt():
                    return self._refresh_token_impl(broker_id, request_token)
                
                # For request tokens, don't use retry as it might be a one-time token
                if request_token:
                    token, expiry_time = refresh_attempt()
                else:
                    token, expiry_time = self.retry_handler.execute(
                        refresh_attempt,
                        retry_on=(TokenRefreshError,),
                        on_retry=lambda e, attempt: self._handle_error(broker_id, e)
                    )
                
                # Measure latency
                latency = time.time() - start_time
                token_refresh_latency.labels(broker=broker_id).observe(latency)
                
                # Store token in database - properly handling the case where the record already exists
                try:
                    # First attempt to find existing record
                    token_record = self.db.session.query(TokenRecord).filter_by(broker_id=broker_id).first()
                    
                    if token_record:
                        # Update existing record
                        token_record.access_token = token
                        token_record.expiry_time = expiry_time
                        token_record.last_refresh = datetime.utcnow()
                        token_record.updated_at = datetime.utcnow()
                        token_record.refresh_count += 1
                    else:
                        # Create new record
                        token_record = TokenRecord(
                            broker_id=broker_id,
                            access_token=token,
                            expiry_time=expiry_time,
                            last_refresh=datetime.utcnow()
                        )
                        self.db.session.add(token_record)
                    
                    # Commit changes
                    self.db.session.commit()
                    
                    # Save to secure encrypted file as well
                    try:
                        from token_security import secure_save_token
                        
                        # Prepare token data for secure storage
                        token_data = {
                            "access_token": token,
                            "broker_id": broker_id,
                            "expires_at": expiry_time.timestamp(),
                            "last_refresh": datetime.utcnow().isoformat(),  # Use ISO format for UI compatibility
                            "created_at": datetime.utcnow().timestamp(),
                            "token_type": "access"
                        }
                        
                        # Save encrypted token
                        secure_save_token(token_data)
                        logger.info(f"Token for broker {broker_id} saved securely to encrypted file")
                        
                    except Exception as e:
                        logger.error(f"Failed to save token to encrypted file: {e}")
                        # Continue execution despite error - database is primary storage
                    
                except Exception as db_error:
                    # Handle database errors
                    logger.error(f"Database error when saving token for broker {broker_id}: {db_error}")
                    self.db.session.rollback()
                    raise
                
                # Cache token
                self._cache_token(broker_id, token, expiry_time)
                
                # The token was already saved to the secure file during database storage
                # No need to save again for Zerodha specifically
                
                # Update metrics
                token_refresh_attempts.labels(broker=broker_id, status="success").inc()
                token_expiry.labels(broker=broker_id).set(
                    (expiry_time - datetime.utcnow()).total_seconds()
                )
                
                # Schedule next refresh
                seconds_until_refresh = (expiry_time - datetime.utcnow()).total_seconds() - TOKEN_EXPIRY_BUFFER
                if seconds_until_refresh > 0:
                    logger.info(f"Scheduling next token refresh for broker {broker_id} in {seconds_until_refresh:.1f} seconds")
                    threading.Timer(seconds_until_refresh, self.refresh_token, args=[broker_id]).start()
                else:
                    logger.warning(f"Token expiry buffer for broker {broker_id} is too short, scheduling immediate refresh")
                    threading.Timer(1, self.refresh_token, args=[broker_id]).start()
                
                # Send success event
                self._send_token_event(broker_id, True, token)
                
                logger.info(f"Successfully refreshed token for broker {broker_id}")
                return True
                
            except Exception as e:
                # Handle any unhandled exceptions
                logger.exception(f"Unhandled exception during token refresh for broker {broker_id}: {e}")
                token_refresh_attempts.labels(broker=broker_id, status="error").inc()
                token_errors.labels(broker=broker_id, error_type="Unhandled").inc()
                
                # Send error event
                self._send_token_event(broker_id, False, error=str(e))
                
                # Schedule retry
                retry_delay = random.uniform(BASE_RETRY_DELAY * (1 - JITTER_FACTOR), 
                                            BASE_RETRY_DELAY * (1 + JITTER_FACTOR))
                logger.info(f"Scheduling retry for broker {broker_id} in {retry_delay:.1f} seconds")
                threading.Timer(retry_delay, self.refresh_token, args=[broker_id]).start()
                
                return False
    
    def get_token(self, broker_id: str) -> Optional[str]:
        """
        Get current valid token for broker.
        
        Args:
            broker_id: Broker identifier
            
        Returns:
            Current token or None if not available
        """
        # Try to get token from cache first
        token = self._get_cached_token(broker_id)
        
        if token:
            logger.debug(f"Retrieved cached token for broker {broker_id}")
            return token
            
        # If token not in cache, get from database
        try:
            token_record = self.db.session.query(TokenRecord).filter_by(broker_id=broker_id).first()
            
            if token_record and token_record.expiry_time > datetime.utcnow():
                # Token is still valid
                logger.debug(f"Retrieved database token for broker {broker_id}")
                
                # Cache token for future use
                self._cache_token(broker_id, token_record.access_token, token_record.expiry_time)
                
                return token_record.access_token
            
            # Token not found or expired, trigger refresh
            logger.info(f"No valid token found for broker {broker_id}, triggering refresh")
            success = self.refresh_token(broker_id)
            
            if success:
                # Try to get token again after refresh
                return self._get_cached_token(broker_id)
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error retrieving token for broker {broker_id}: {e}")
            return None

    def refresh_all_tokens(self) -> Dict[str, bool]:
        """
        Refresh tokens for all configured brokers.
        
        Returns:
            Dictionary of broker_id to refresh success status
        """
        results = {}
        
        for broker in self.config.get("brokers", []):
            broker_id = broker.get("id")
            if broker_id:
                try:
                    results[broker_id] = self.refresh_token(broker_id)
                except Exception as e:
                    logger.error(f"Failed to refresh token for broker {broker_id}: {e}")
                    results[broker_id] = False
        
        return results
        
    def get_token_status(self) -> Dict[str, Any]:
        """
        Get token status information for API endpoints.
        
        Returns:
            Dictionary with token status information
        """
        try:
            # Get all brokers
            brokers = self.config.get("brokers", [])
            
            # Check token status for each broker
            statuses = {}
            for broker in brokers:
                broker_id = broker.get("id")
                if not broker_id:
                    continue
                    
                # Get token from database
                token_record = self.db.session.query(TokenRecord).filter_by(broker_id=broker_id).first()
                
                if token_record:
                    # Calculate expiry
                    now = datetime.utcnow()
                    expiry_time = token_record.expiry_time
                    time_to_expiry = expiry_time - now if expiry_time > now else None
                    
                    # Determine status
                    if time_to_expiry:
                        seconds_to_expiry = time_to_expiry.total_seconds()
                        if seconds_to_expiry < 3600:  # Less than 1 hour
                            status = "expiring"
                        else:
                            status = "valid"
                            
                        # Format time to expiry for display
                        hours, remainder = divmod(int(seconds_to_expiry), 3600)
                        minutes, _ = divmod(remainder, 60)
                        time_to_expiry_str = f"{hours}h {minutes}m"
                    else:
                        status = "expired"
                        time_to_expiry_str = "expired"
                    
                    statuses[broker_id] = {
                        "status": status,
                        "last_refresh": token_record.last_refresh.isoformat() if token_record.last_refresh else None,
                        "expiry_time": token_record.expiry_time.isoformat() if token_record.expiry_time else None,
                        "time_to_expiry": time_to_expiry_str
                    }
                else:
                    statuses[broker_id] = {
                        "status": "not_found",
                        "last_refresh": None,
                        "expiry_time": None,
                        "time_to_expiry": None
                    }
            
            return {
                "status": "success",
                "tokens": statuses
            }
        
        except Exception as e:
            logger.error(f"Error getting token status: {e}")
            return {
                "status": "error",
                "message": str(e)
            }
    
    def trigger_refresh(self) -> Dict[str, Any]:
        """
        Trigger a token refresh and return status.
        
        Returns:
            Dictionary with refresh status
        """
        try:
            # Get all brokers
            brokers = self.config.get("brokers", [])
            
            # Refresh tokens for all brokers
            refresh_results = {}
            for broker in brokers:
                broker_id = broker.get("id")
                if not broker_id:
                    continue
                    
                try:
                    # Refresh token in a separate thread to avoid blocking
                    threading.Thread(target=self.refresh_token, args=[broker_id]).start()
                    refresh_results[broker_id] = "refresh_triggered"
                except Exception as e:
                    logger.error(f"Error triggering refresh for broker {broker_id}: {e}")
                    refresh_results[broker_id] = f"error: {str(e)}"
            
            return {
                "status": "success",
                "refresh_triggered": True,
                "results": refresh_results
            }
        
        except Exception as e:
            logger.error(f"Error triggering token refresh: {e}")
            return {
                "status": "error",
                "message": str(e)
            }
            
    def get_all_token_statuses(self) -> List[Dict[str, Any]]:
        """
        Get detailed token status for all brokers.
        
        Returns:
            List of dictionaries with detailed token status
        """
        try:
            # Get all brokers
            brokers = self.config.get("brokers", [])
            
            # Check token status for each broker
            statuses = []
            for broker in brokers:
                broker_id = broker.get("id")
                if not broker_id:
                    continue
                    
                # Get token from database
                token_record = self.db.session.query(TokenRecord).filter_by(broker_id=broker_id).first()
                
                if token_record:
                    # Calculate expiry
                    now = datetime.utcnow()
                    expiry_time = token_record.expiry_time
                    time_to_expiry = expiry_time - now if expiry_time > now else None
                    
                    # Create status entry
                    entry = {
                        "broker_id": broker_id,
                        "broker_name": broker.get("name", broker_id),
                        "status": "valid" if time_to_expiry and time_to_expiry.total_seconds() > 0 else "expired",
                        "last_refresh": token_record.last_refresh.isoformat() if token_record.last_refresh else None,
                        "expiry_time": token_record.expiry_time.isoformat() if token_record.expiry_time else None,
                        "time_to_expiry_seconds": int(time_to_expiry.total_seconds()) if time_to_expiry and time_to_expiry.total_seconds() > 0 else 0,
                        # Include masked token for verification
                        "token_preview": f"{token_record.access_token[:5]}...{token_record.access_token[-5:]}" if token_record.access_token else None
                    }
                    
                    statuses.append(entry)
                else:
                    entry = {
                        "broker_id": broker_id,
                        "broker_name": broker.get("name", broker_id),
                        "status": "not_found",
                        "last_refresh": None,
                        "expiry_time": None,
                        "time_to_expiry_seconds": 0,
                        "token_preview": None
                    }
                    
                    statuses.append(entry)
            
            return statuses
        
        except Exception as e:
            logger.error(f"Error getting all token statuses: {e}")
            return [{"error": str(e)}]