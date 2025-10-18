"""
Application Module
----------------
Initializes the application and its components.
"""

import logging
from typing import Dict, Any, Optional

# Local imports
from core.token.manager import TokenManager
from core.token.service import TokenService

# Configure logging
from core.utils.logger import get_logger
logger = get_logger("auth_app")

class Application:
    """
    Main application class that orchestrates components.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize application.
        
        Args:
            config: Application configuration
        """
        self.config = config or {}
        self.token_manager = None
        self.token_service = None
    
    def initialize(self):
        """Initialize application components."""
        logger.info("Initializing application components")
        
        # Initialize token manager
        self.token_manager = TokenManager(
            config_path=self.config.get("broker_config_path", "config/broker_config.yaml")
        )
        
        # Initialize token service
        self.token_service = TokenService()
        
        logger.info("Application components initialized successfully")
        
    def start(self):
        """Start application."""
        if not self.token_service:
            self.initialize()
            
        logger.info("Starting application services")
        self.token_service.start()