#!/usr/bin/env python3
"""
Main entry point for Auth Service.
Uses the modular application structure.
"""

import sys
import logging
from pathlib import Path

# Add parent directory to path to resolve imports
parent_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(parent_dir))

# Import application
from services.auth_service.lib.application import Application
from core.utils.logger import setup_logging

# Configure logging
setup_logging("config/logging.yaml")
logger = logging.getLogger("auth_service_main")

def main():
    """Main entry point."""
    try:
        logger.info("Starting Auth Service")
        
        # Initialize application
        app = Application()
        app.initialize()
        
        # Start application
        app.start()
        
    except KeyboardInterrupt:
        logger.info("Auth Service stopped by user")
    except Exception as e:
        logger.error(f"Auth Service failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()