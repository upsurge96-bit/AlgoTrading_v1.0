import time
import functools
from core.utils.logger import get_logger

logger = get_logger("retry_util")

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
