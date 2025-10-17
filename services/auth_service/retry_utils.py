#!/usr/bin/env python3
"""
retry_utils.py
------------
Robust retry utilities for API calls and error handling.
"""

import time
import random
import logging
import functools
from typing import Callable, Any, TypeVar, Dict, Optional, List, Tuple, Union
from requests.exceptions import RequestException, Timeout, ConnectionError

# Configure logger
logger = logging.getLogger("retry_utils")

# Type variable for function return types
T = TypeVar('T')

class RetryException(Exception):
    """Exception raised when all retries have failed."""
    
    def __init__(self, original_exception: Exception, attempts: int):
        self.original_exception = original_exception
        self.attempts = attempts
        message = f"Failed after {attempts} attempts. Last error: {str(original_exception)}"
        super().__init__(message)


def retry(
    max_retries: int = 3,
    initial_backoff: float = 1.0,
    max_backoff: float = 60.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    retry_on_exceptions: Tuple[Exception, ...] = (RequestException, ConnectionError, Timeout),
    retry_on_status_codes: Tuple[int, ...] = (429, 500, 502, 503, 504),
    fallback: Optional[Callable[..., T]] = None
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Retry decorator with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        initial_backoff: Initial backoff time in seconds
        max_backoff: Maximum backoff time in seconds
        backoff_factor: Factor by which to increase backoff after each attempt
        jitter: Whether to add randomness to backoff times
        retry_on_exceptions: Exceptions that trigger retries
        retry_on_status_codes: HTTP status codes that trigger retries
        fallback: Function to call if all retries fail
        
    Returns:
        Decorator function
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            attempts = 0
            last_exception = None
            
            while attempts <= max_retries:
                try:
                    result = func(*args, **kwargs)
                    
                    # Check for error response with status code
                    if hasattr(result, 'status_code') and result.status_code in retry_on_status_codes:
                        last_exception = RequestException(f"Received status code {result.status_code}")
                        logger.warning(f"Retry-worthy status code {result.status_code}, retrying...")
                    else:
                        # Success
                        return result
                    
                except retry_on_exceptions as e:
                    last_exception = e
                    logger.warning(f"Exception during execution: {str(e)}, retrying...")
                
                # If we get here, either we got a retry-worthy status code or an exception
                attempts += 1
                
                if attempts > max_retries:
                    # All retries failed
                    logger.error(f"All {max_retries} retries failed. Last error: {str(last_exception)}")
                    if fallback:
                        logger.info("Using fallback function")
                        return fallback(*args, **kwargs)
                    else:
                        raise RetryException(last_exception, attempts)
                
                # Calculate backoff time
                backoff_time = min(initial_backoff * (backoff_factor ** (attempts - 1)), max_backoff)
                
                # Add jitter if enabled (±20%)
                if jitter:
                    backoff_time = backoff_time * random.uniform(0.8, 1.2)
                
                logger.info(f"Retrying in {backoff_time:.2f} seconds... (attempt {attempts}/{max_retries})")
                time.sleep(backoff_time)
            
            # This should never be reached due to the raise above, but just in case
            raise RetryException(last_exception or Exception("Unknown error"), attempts)
        
        return wrapper
    
    return decorator


def with_circuit_breaker(
    failure_threshold: int = 5,
    reset_timeout: float = 60.0,
    half_open_timeout: float = 30.0,
    exceptions_to_monitor: Tuple[Exception, ...] = (Exception,),
    fallback: Optional[Callable[..., T]] = None
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Circuit breaker pattern implementation.
    
    Args:
        failure_threshold: Number of failures before opening the circuit
        reset_timeout: Time in seconds to wait before trying to half-close the circuit
        half_open_timeout: Time in seconds to wait in half-open state
        exceptions_to_monitor: Exceptions that count as failures
        fallback: Function to call when circuit is open
        
    Returns:
        Decorator function
    """
    # Shared circuit state (class level)
    circuit_state = {
        "status": "closed",  # closed, open, half-open
        "failures": 0,
        "last_failure_time": 0,
        "last_success_time": 0,
    }
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            current_time = time.time()
            
            # Check if circuit is open
            if circuit_state["status"] == "open":
                if current_time - circuit_state["last_failure_time"] > reset_timeout:
                    logger.info("Circuit half-closing after timeout")
                    circuit_state["status"] = "half-open"
                else:
                    if fallback:
                        logger.info("Circuit open, using fallback")
                        return fallback(*args, **kwargs)
                    else:
                        raise Exception("Circuit breaker open")
            
            # Try to execute function
            try:
                result = func(*args, **kwargs)
                
                # Success - reset or close the circuit
                if circuit_state["status"] == "half-open":
                    if current_time - circuit_state["last_success_time"] > half_open_timeout:
                        logger.info("Circuit fully closing after successful half-open period")
                        circuit_state["status"] = "closed"
                        circuit_state["failures"] = 0
                    circuit_state["last_success_time"] = current_time
                elif circuit_state["status"] == "closed":
                    circuit_state["failures"] = 0
                
                return result
                
            except exceptions_to_monitor as e:
                # Failure - increment counter and maybe open circuit
                circuit_state["failures"] += 1
                circuit_state["last_failure_time"] = current_time
                
                if circuit_state["failures"] >= failure_threshold or circuit_state["status"] == "half-open":
                    logger.warning(f"Circuit opening after {circuit_state['failures']} failures")
                    circuit_state["status"] = "open"
                
                # Re-raise the exception
                raise
        
        return wrapper
    
    return decorator