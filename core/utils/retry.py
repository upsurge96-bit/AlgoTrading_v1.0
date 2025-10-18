import time
import random
import functools
from typing import Callable, Type, TypeVar, Any, Optional, Union, Tuple
from core.utils.logger import get_logger

logger = get_logger("retry_util")

class RetryException(Exception):
    """Exception raised when a retryable operation fails after all attempts."""
    pass

def retry(exceptions, tries=3, delay=1, backoff=2):
    """Generic retry decorator with exponential backoff."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            attempt, wait = 1, delay
            while attempt <= tries:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    logger.warning(f"Attempt {attempt}/{tries} failed: {e}")
                    if attempt == tries:
                        raise
                    time.sleep(wait)
                    attempt += 1
                    wait *= backoff
        return wrapper
    return decorator

T = TypeVar('T')
E = TypeVar('E', bound=Exception)

class RetryWithExponentialBackoff:
    """Class-based retry handler with advanced exponential backoff.
    
    Features:
      - Configurable retry parameters
      - Exponential backoff with jitter
      - Custom error handlers
      - Circuit breaker pattern
    
    Usage:
        retry_handler = RetryWithExponentialBackoff(
            max_attempts=5,
            base_delay=1.0,
            max_delay=60.0,
            jitter_factor=0.2
        )
        
        result = retry_handler.execute(
            func=my_function,
            args=(arg1, arg2),
            kwargs={"param": "value"},
            retry_on=(RequestError, TimeoutError),
            on_retry=lambda e, attempt: log_error(e, attempt)
        )
    """
    
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        jitter_factor: float = 0.1,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_timeout: float = 60.0
    ):
        """
        Initialize retry handler.
        
        Args:
            max_attempts: Maximum number of retry attempts
            base_delay: Base delay between retries (seconds)
            max_delay: Maximum delay between retries (seconds)
            jitter_factor: Random jitter factor (0.0-1.0)
            circuit_breaker_threshold: Number of consecutive failures before circuit opens
            circuit_breaker_timeout: Time to keep circuit open (seconds)
        """
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter_factor = jitter_factor
        self.circuit_breaker_threshold = circuit_breaker_threshold
        self.circuit_breaker_timeout = circuit_breaker_timeout
        
        # Circuit breaker state
        self.failure_count = 0
        self.circuit_open = False
        self.circuit_open_time = 0
    
    def _calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay with exponential backoff and jitter.
        
        Args:
            attempt: Current attempt number (1-based)
            
        Returns:
            Delay in seconds
        """
        # Calculate base exponential backoff
        delay = min(self.base_delay * (2 ** (attempt - 1)), self.max_delay)
        
        # Apply jitter
        jitter = random.uniform(-self.jitter_factor, self.jitter_factor) * delay
        delay = delay + jitter
        
        return delay
    
    def _check_circuit_breaker(self) -> bool:
        """
        Check if circuit breaker is open.
        
        Returns:
            True if circuit is closed (requests allowed), False if open
        """
        # If circuit is open, check if timeout has elapsed
        if self.circuit_open:
            if time.time() - self.circuit_open_time > self.circuit_breaker_timeout:
                # Close the circuit (half-open state)
                self.circuit_open = False
                self.failure_count = 0
                logger.info("Circuit breaker reset (timeout elapsed)")
                return True
            else:
                # Circuit still open
                return False
        
        # Circuit closed
        return True
    
    def _update_circuit_breaker(self, success: bool) -> None:
        """
        Update circuit breaker state based on request outcome.
        
        Args:
            success: Whether the request was successful
        """
        if success:
            # Reset failure count on success
            self.failure_count = 0
            if self.circuit_open:
                # Close circuit if in half-open state
                self.circuit_open = False
                logger.info("Circuit breaker closed (request succeeded)")
        else:
            # Increment failure count
            self.failure_count += 1
            
            # Open circuit if threshold reached
            if self.failure_count >= self.circuit_breaker_threshold:
                self.circuit_open = True
                self.circuit_open_time = time.time()
                logger.warning(f"Circuit breaker opened (failures: {self.failure_count})")
    
    def execute(
        self,
        func: Callable[..., T],
        args: Tuple = (),
        kwargs: Optional[dict] = None,
        retry_on: Union[Type[Exception], Tuple[Type[Exception], ...]] = Exception,
        on_retry: Optional[Callable[[Exception, int], None]] = None
    ) -> T:
        """
        Execute function with retry.
        
        Args:
            func: Function to execute
            args: Positional arguments to pass to function
            kwargs: Keyword arguments to pass to function
            retry_on: Exception(s) to retry on
            on_retry: Callback for retry events (error, attempt)
            
        Returns:
            Function result
            
        Raises:
            Exception: If max attempts exceeded or non-retryable exception
        """
        kwargs = kwargs or {}
        attempt = 1
        
        while True:
            # Check circuit breaker
            if not self._check_circuit_breaker():
                logger.warning("Circuit breaker open, failing fast")
                raise RuntimeError("Circuit breaker open")
            
            try:
                # Execute function
                result = func(*args, **kwargs)
                
                # Update circuit breaker on success
                self._update_circuit_breaker(True)
                
                return result
                
            except retry_on as e:
                # Check if max attempts reached
                if attempt >= self.max_attempts:
                    # Update circuit breaker on final failure
                    self._update_circuit_breaker(False)
                    logger.error(f"Max retry attempts ({self.max_attempts}) reached")
                    raise
                
                # Calculate delay
                delay = self._calculate_delay(attempt)
                
                # Call on_retry callback
                if on_retry:
                    try:
                        on_retry(e, attempt)
                    except Exception as callback_err:
                        logger.warning(f"Error in retry callback: {callback_err}")
                
                logger.warning(f"Attempt {attempt}/{self.max_attempts} failed: {e}. Retrying in {delay:.2f}s")
                
                # Wait before retry
                time.sleep(delay)
                
                # Increment attempt counter
                attempt += 1
                
            except Exception as e:
                # Non-retryable exception
                # Update circuit breaker on failure
                self._update_circuit_breaker(False)
                raise
