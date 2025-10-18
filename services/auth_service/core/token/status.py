"""
Token Status Module
-----------------
Module for checking and monitoring token status.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

# Setup logging
from core.utils.logger import get_logger
logger = get_logger("token_status")

@dataclass
class TokenStatus:
    """Token status information."""
    broker_id: str
    is_valid: bool
    expires_in: Optional[int] = None  # seconds until expiry, None if expired
    last_refresh: Optional[datetime] = None
    status: str = "unknown"  # "valid", "expiring", "expired", "unknown"
    error: Optional[str] = None

def format_time_remaining(seconds: Optional[int]) -> str:
    """
    Format time remaining in human-readable format.
    
    Args:
        seconds: Seconds remaining or None
        
    Returns:
        Human-readable time string
    """
    if seconds is None:
        return "N/A"
        
    if seconds <= 0:
        return "Expired"
        
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0 or days > 0:
        parts.append(f"{hours}h")
    if minutes > 0 or hours > 0 or days > 0:
        parts.append(f"{minutes}m")
    parts.append(f"{seconds}s")
    
    return " ".join(parts)

def get_token_status_label(expires_in: Optional[int]) -> str:
    """
    Get status label based on expiry time.
    
    Args:
        expires_in: Seconds until token expiry
        
    Returns:
        Status label: "valid", "expiring", "expired", or "unknown"
    """
    if expires_in is None:
        return "unknown"
        
    if expires_in <= 0:
        return "expired"
        
    if expires_in < 3600:  # Less than 1 hour
        return "expiring"
        
    return "valid"