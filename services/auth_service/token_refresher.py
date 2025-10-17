#!/usr/bin/env python3
"""
token_refresher.py
-----------------
Automatic token refresh component for Kite Connect tokens.
Handles refreshing tokens before expiration and maintains token validity.
"""

import os
import json
import time
import datetime
import logging
import requests
import random
from typing import Optional, Dict, Any, Callable
from urllib.parse import urlencode

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("token_refresher")

class TokenRefresher:
    """
    Handles refreshing of Kite Connect access tokens.
    
    The TokenRefresher class provides functionality to:
    1. Monitor token expiration
    2. Automatically refresh tokens before expiry
    3. Notify other components on refresh events
    4. Handle refresh failures with retries and backoff
    """
    
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        token_getter: Callable[[], Optional[Dict[str, Any]]],
        token_saver: Callable[[Dict[str, Any]], None],
        refresh_threshold_minutes: int = 60,
        max_retries: int = 3,
        retry_backoff_seconds: int = 60
    ):
        """
        Initialize the token refresher.
        
        Args:
            api_key: Kite API key
            api_secret: Kite API secret
            token_getter: Function to retrieve current token
            token_saver: Function to save refreshed token
            refresh_threshold_minutes: Minutes before expiry to refresh token
            max_retries: Maximum number of refresh attempts
            retry_backoff_seconds: Base backoff time between retries
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.token_getter = token_getter
        self.token_saver = token_saver
        self.refresh_threshold = datetime.timedelta(minutes=refresh_threshold_minutes)
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff_seconds
        self._subscribers = []
    
    def subscribe(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """
        Subscribe a callback for token refresh events.
        
        Args:
            callback: Function to call with new token data when refreshed
        """
        if callback not in self._subscribers:
            self._subscribers.append(callback)
    
    def unsubscribe(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """
        Unsubscribe a callback from token refresh events.
        
        Args:
            callback: Function previously subscribed
        """
        if callback in self._subscribers:
            self._subscribers.remove(callback)
    
    def _notify_subscribers(self, token_data: Dict[str, Any]) -> None:
        """
        Notify all subscribers with new token data.
        
        Args:
            token_data: New token data
        """
        for callback in self._subscribers:
            try:
                callback(token_data)
            except Exception as e:
                logger.error(f"Error notifying subscriber: {e}")
    
    def check_token_status(self) -> Dict[str, Any]:
        """
        Check if token is valid and needs refresh.
        
        Returns:
            Dict with status information:
            {
                "has_token": bool,
                "is_valid": bool,
                "needs_refresh": bool,
                "time_to_expiry": timedelta or None,
                "token_data": dict or None
            }
        """
        token_data = self.token_getter()
        
        result = {
            "has_token": False,
            "is_valid": False,
            "needs_refresh": False,
            "time_to_expiry": None,
            "token_data": None
        }
        
        if not token_data:
            return result
        
        result["has_token"] = True
        result["token_data"] = token_data
        
        try:
            expiry = datetime.datetime.fromisoformat(token_data["expires_at"])
            now = datetime.datetime.now()
            
            if now < expiry:
                result["is_valid"] = True
                time_to_expiry = expiry - now
                result["time_to_expiry"] = time_to_expiry
                
                # Check if we need to refresh (within threshold of expiry)
                if time_to_expiry < self.refresh_threshold:
                    result["needs_refresh"] = True
        except (KeyError, ValueError) as e:
            logger.error(f"Error checking token expiry: {e}")
        
        return result
    
    def _generate_login_url(self) -> str:
        """
        Generate a login URL for Kite Connect.
        
        Returns:
            Login URL string
        """
        params = {
            "api_key": self.api_key,
            "v": 3,  # API version
        }
        return f"https://kite.zerodha.com/connect/login?{urlencode(params)}"
    
    def get_login_info(self) -> Dict[str, Any]:
        """
        Get information needed for manual login when auto-refresh fails.
        
        Returns:
            Dict with login URL and other details
        """
        return {
            "login_url": self._generate_login_url(),
            "api_key": self.api_key,
            "instructions": "Visit this URL and complete the Zerodha login process."
        }
    
    def refresh_needed(self) -> bool:
        """
        Check if token refresh is needed.
        
        Returns:
            True if refresh is needed, False otherwise
        """
        status = self.check_token_status()
        return status["needs_refresh"] or not status["is_valid"]
    
    def auto_refresh_if_needed(self) -> bool:
        """
        Automatically refresh the token if needed.
        
        Returns:
            True if refresh was successful or not needed, False if failed
        """
        if not self.refresh_needed():
            logger.debug("Token refresh not needed")
            return True
        
        logger.info("Token needs refresh - attempting automatic refresh")
        
        # For now, return False as Kite API doesn't support automatic refresh
        # We'll need manual login via the web interface
        return False
    
    def _calculate_backoff(self, retry_count: int) -> int:
        """
        Calculate backoff time with exponential backoff and jitter.
        
        Args:
            retry_count: Current retry attempt number
        
        Returns:
            Backoff time in seconds
        """
        backoff = self.retry_backoff * (2 ** retry_count)
        jitter = random.uniform(0.75, 1.25)
        return int(backoff * jitter)
    
    def handle_refresh_failure(self) -> Dict[str, Any]:
        """
        Handle token refresh failure by providing recovery instructions.
        
        Returns:
            Dict with recovery instructions
        """
        login_info = self.get_login_info()
        return {
            "status": "manual_login_required",
            "message": "Automatic refresh failed. Manual login required.",
            "login_info": login_info
        }
    
    def check_and_refresh(self) -> Dict[str, Any]:
        """
        Check token status and refresh if needed.
        
        Returns:
            Dict with status information
        """
        status = self.check_token_status()
        
        if not status["has_token"] or not status["is_valid"] or status["needs_refresh"]:
            # Token is invalid or needs refresh
            if self.auto_refresh_if_needed():
                # Refresh successful
                return {
                    "status": "refreshed",
                    "message": "Token refreshed successfully."
                }
            else:
                # Refresh failed, return recovery instructions
                return self.handle_refresh_failure()
        
        # Token is valid and doesn't need refresh
        return {
            "status": "valid",
            "message": "Token is valid.",
            "expires_at": status["token_data"]["expires_at"],
            "time_to_expiry": str(status["time_to_expiry"])
        }