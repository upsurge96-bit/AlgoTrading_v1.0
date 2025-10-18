"""
Core Utilities Package
======================

Centralized utilities for the AlgoTrading platform.

Usage:
    from core.utils.logger import get_logger, setup_logging
    from core.utils.config_loader import load_config

    # Or use convenience imports
    from core import get_logger, load_config
"""

# Convenience imports for commonly used utilities
from core.utils.logger import get_logger, setup_logging
from core.utils.config_loader import load_config

__all__ = [
    'get_logger',
    'setup_logging',
    'load_config',
]

__version__ = '1.0.0'
