#!/usr/bin/env python3
"""
Token Refresher Service
-----------------------
Service responsible for managing authentication tokens with brokers.
Implements smart retry mechanisms, failure handling, and idempotency.
"""

import os
import sys
import time
import json
import logging
import threading
import traceback
import random
from typing import Dict, Any, List, Optional, Tuple, Callable
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path

# Add parent directory to path to resolve imports
parent_dir = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(parent_dir))

# Core imports
from core.utils.config_loader import ConfigLoader
from core.utils.logger import setup_logging
from core.utils.metrics import metrics_registry, push_to_prometheus
from core.utils.retry import RetryWithExponentialBackoff
from core.messaging.kafka_client import KafkaProducer
from core.messaging.redis_client import RedisClient
from core.db.connector import DatabaseConnector
from core.db.models import TokenRecord

# Local imports
from idempotency import idempotent

# Constants
DEFAULT_CONFIG_PATH = "config/broker_config.yaml"
DEFAULT_LOG_CONFIG = "config/logging.yaml"
TOKEN_EXPIRY_BUFFER = 300  # 5 minutes in seconds
MAX_RETRY_ATTEMPTS = 5
BASE_RETRY_DELAY = 2  # seconds
MAX_RETRY_DELAY = 300  # 5 minutes in seconds
JITTER_FACTOR = 0.2  # 20% jitter
TOKEN_REFRESH_TOPIC = "auth.token.refresh"
TOKEN_ERROR_TOPIC = "auth.token.error"

# Configure logging
setup_logging(DEFAULT_LOG_CONFIG)
logger = logging.getLogger("token_refresher")

# Metrics
token_refresh_attempts = metrics_registry.counter(
    "token_refresh_attempts_total",
    "Total number of token refresh attempts",
    ["broker", "status"]
)
token_refresh_latency = metrics_registry.histogram(
    "token_refresh_latency_seconds",
    "Token refresh latency in seconds",
    ["broker"]
)
token_expiry = metrics_registry.gauge(
    "token_expiry_seconds",
    "Seconds until token expiry",
    ["broker"]
)
token_errors = metrics_registry.counter(
    "token_errors_total",
    "Total number of token errors",
    ["broker", "error_type"]
)

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
            config_loader = ConfigLoader()
            return config_loader.load_config(self.config_path)
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
            self.kafka_producer.send(topic, json.dumps(event))
            
        except Exception as e:
            logger.error(f"Failed to send token event: {e}")
    
    def _refresh_token_impl(self, broker_id: str) -> Tuple[str, datetime]:
        """
        Actual implementation of token refresh.
        
        Args:
            broker_id: Broker identifier
            
        Returns:
            Tuple of (token, expiry_time)
            
        Raises:
            TokenRefreshError: If token refresh fails
        """
        # This is a stub implementation
        # In a real system, this would call the broker's API to refresh the token
        broker_config = self._get_broker_config(broker_id)
        
        if not broker_config:
            raise UnknownError(f"No configuration found for broker {broker_id}")
        
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
    
    @idempotent(lambda self, broker_id: f"token_refresh:{broker_id}")
    def refresh_token(self, broker_id: str) -> bool:
        """
        Refresh token for a specific broker.
        
        Args:
            broker_id: Broker identifier
            
        Returns:
            True if token refresh was successful, False otherwise
        """
        logger.info(f"Starting token refresh for broker {broker_id}")
        
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
                    return self._refresh_token_impl(broker_id)
                
                token, expiry_time = self.retry_handler.execute(
                    refresh_attempt,
                    retry_on=(TokenRefreshError,),
                    on_retry=lambda e, attempt: self._handle_error(broker_id, e)
                )
                
                # Measure latency
                latency = time.time() - start_time
                token_refresh_latency.labels(broker=broker_id).observe(latency)
                
                # Store token in database
                self.db.session.merge(TokenRecord(
                    broker_id=broker_id,
                    access_token=token,
                    expiry_time=expiry_time,
                    last_refresh=datetime.utcnow()
                ))
                self.db.session.commit()
                
                # Cache token
                self._cache_token(broker_id, token, expiry_time)
                
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

def main():
    """Main entry point for token refresher service."""
    try:
        logger.info("Starting Token Refresher Service")
        
        # Initialize token manager
        token_manager = TokenManager()
        
        # Refresh all tokens on startup
        token_manager.refresh_all_tokens()
        
        # Keep service running
        while True:
            # Push metrics to Prometheus
            push_to_prometheus()
            
            # Sleep for a while
            time.sleep(60)
            
    except KeyboardInterrupt:
        logger.info("Token Refresher Service stopped by user")
    except Exception as e:
        logger.critical(f"Token Refresher Service failed: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()