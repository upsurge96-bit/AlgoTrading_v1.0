#!/usr/bin/env python3
"""
idempotency.py
-------------
Provides idempotency support for token generation operations.
"""

import time
import json
import hashlib
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Callable
from functools import wraps

# Setup logging
logger = logging.getLogger("idempotency")

# Constants
IDEMPOTENCY_STORE_FILE = Path("data/idempotency_store.json")
IDEMPOTENCY_EXPIRY = 86400  # 24 hours in seconds

class IdempotencyStore:
    """
    Idempotency store for token operations.
    
    This is a simple file-based implementation. In production,
    consider using Redis or another distributed store.
    """
    
    def __init__(self, store_file: Path = IDEMPOTENCY_STORE_FILE):
        self.store_file = store_file
        self._store: Dict[str, Dict[str, Any]] = {}
        self._load_store()
    
    def _load_store(self) -> None:
        """Load idempotency store from file."""
        if self.store_file.exists():
            try:
                self._store = json.loads(self.store_file.read_text())
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Failed to load idempotency store: {e}")
                self._store = {}
        else:
            self._store = {}
    
    def _save_store(self) -> None:
        """Save idempotency store to file."""
        try:
            # Create directory if needed
            self.store_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Save store
            self.store_file.write_text(json.dumps(self._store))
        except IOError as e:
            logger.error(f"Failed to save idempotency store: {e}")
    
    def _clean_expired(self) -> None:
        """Remove expired entries from store."""
        now = time.time()
        expired = []
        
        for key, entry in self._store.items():
            if entry.get("expires_at", 0) < now:
                expired.append(key)
        
        for key in expired:
            del self._store[key]
        
        if expired:
            logger.info(f"Cleaned {len(expired)} expired idempotency keys")
            self._save_store()
    
    def has_key(self, key: str) -> bool:
        """
        Check if idempotency key exists.
        
        Args:
            key: Idempotency key
            
        Returns:
            True if key exists and is not expired
        """
        self._clean_expired()
        return key in self._store
    
    def get_result(self, key: str) -> Optional[Any]:
        """
        Get stored result for idempotency key.
        
        Args:
            key: Idempotency key
            
        Returns:
            Stored result or None if not found
        """
        if not self.has_key(key):
            return None
        
        return self._store[key].get("result")
    
    def store_result(self, key: str, result: Any, expires_in: int = IDEMPOTENCY_EXPIRY) -> None:
        """
        Store result for idempotency key.
        
        Args:
            key: Idempotency key
            result: Result to store
            expires_in: Seconds until key expires
        """
        self._store[key] = {
            "result": result,
            "created_at": time.time(),
            "expires_at": time.time() + expires_in
        }
        self._save_store()


# Global idempotency store
_store = IdempotencyStore()

def idempotent(key_func: Callable[[Any, Any], str] = None):
    """
    Decorator to make a function idempotent.
    
    Args:
        key_func: Function to generate idempotency key from arguments
            If None, a hash of the arguments will be used
    
    Returns:
        Decorator function
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate idempotency key
            if key_func:
                idempotency_key = key_func(*args, **kwargs)
            else:
                # Create a hash of the function name and arguments
                arg_str = json.dumps([func.__name__, str(args), str(kwargs)], sort_keys=True)
                idempotency_key = hashlib.sha256(arg_str.encode()).hexdigest()
            
            # Check if we've already processed this request
            if _store.has_key(idempotency_key):
                logger.info(f"Returning cached result for idempotency key {idempotency_key}")
                return _store.get_result(idempotency_key)
            
            # Execute function and store result
            result = func(*args, **kwargs)
            _store.store_result(idempotency_key, result)
            return result
        
        return wrapper
    
    return decorator