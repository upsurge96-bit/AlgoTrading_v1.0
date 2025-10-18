"""
Retry Module
-----------
DEPRECATED: This module is deprecated and will be removed in a future release.
Please use core.utils.retry instead.
"""

import time
import random
import functools
from typing import Callable, Type, TypeVar, Any, Optional, Union, Tuple
import logging

# Import the core retry module
from core.utils.retry import (
    RetryException, 
    retry as core_retry, 
    RetryWithExponentialBackoff
)

# Setup basic logging until the real logger is initialized
logger = logging.getLogger("retry_util")

# Re-export the core retry functionality
__all__ = ['retry', 'RetryException', 'RetryWithExponentialBackoff']

# Define the retry decorator as a pass-through to core.utils.retry
retry = core_retry