"""
Auth Service Client
Fetches access tokens from the auth service
"""

import os
import requests
import logging
from typing import Optional, Dict
from datetime import datetime

logger = logging.getLogger(__name__)


class AuthClient:
    """Client to interact with auth service for tokens"""
    
    def __init__(self, auth_service_url: Optional[str] = None, admin_api_key: Optional[str] = None):
        self.auth_service_url = auth_service_url or os.getenv("AUTH_SERVICE_URL", "http://auth_service:8018")
        self.admin_api_key = admin_api_key or os.getenv("ADMIN_API_KEY", "change-me-in-production")
        self._cached_token: Optional[Dict] = None
        self._cache_time: Optional[datetime] = None
        
    def get_token(self, force_refresh: bool = False) -> Optional[Dict]:
        """
        Get access token from auth service
        
        Args:
            force_refresh: Force fetch from auth service even if cached
            
        Returns:
            Dict with token details or None if failed
        """
        # Return cached token if available and not expired
        if not force_refresh and self._cached_token and self._is_cache_valid():
            logger.debug("Returning cached token")
            return self._cached_token
            
        # Fetch from auth service
        try:
            headers = {
                "X-Admin-API-Key": self.admin_api_key
            }
            
            url = f"{self.auth_service_url}/admin/token"
            logger.info(f"Fetching token from auth service: {url}")
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get("status") == "success":
                token_data = data.get("data", {})
                self._cached_token = token_data
                self._cache_time = datetime.now()
                logger.info("Successfully fetched token from auth service")
                return token_data
            else:
                logger.error(f"Auth service returned error: {data}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"Failed to fetch token from auth service: {e}")
            return None
            
    def get_access_token(self) -> Optional[str]:
        """
        Get just the access token string
        
        Returns:
            Access token string or None
        """
        token_data = self.get_token()
        if token_data:
            return token_data.get("access_token")
        return None
        
    def get_api_key(self) -> str:
        """
        Get Kite API key from environment
        
        Returns:
            API key string
        """
        return os.getenv("KITE_API_KEY", "")
        
    def _is_cache_valid(self) -> bool:
        """Check if cached token is still valid"""
        if not self._cache_time or not self._cached_token:
            return False
            
        # Cache for 5 minutes
        age = (datetime.now() - self._cache_time).total_seconds()
        if age > 300:
            return False
            
        # Check expiry time
        expires_at = self._cached_token.get("expires_at")
        if expires_at:
            try:
                # Parse expiry time
                if isinstance(expires_at, str):
                    from dateutil import parser
                    expiry_dt = parser.parse(expires_at)
                else:
                    expiry_dt = datetime.fromtimestamp(float(expires_at))
                    
                # Check if expired (with 5 minute buffer)
                from datetime import timedelta
                if expiry_dt < datetime.now() + timedelta(minutes=5):
                    logger.info("Cached token expired or about to expire")
                    return False
            except Exception as e:
                logger.warning(f"Failed to parse expiry time: {e}")
                return False
                
        return True
        
    def health_check(self) -> bool:
        """
        Check if auth service is healthy
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            url = f"{self.auth_service_url}/health"
            response = requests.get(url, timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Auth service health check failed: {e}")
            return False
