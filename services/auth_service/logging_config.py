#!/usr/bin/env python3
"""
logging_config.py
----------------
Enhanced JSON logging configuration for production use.
"""

import os
import sys
import logging
import json
from pathlib import Path
from typing import Dict, Any, Optional

from pythonjsonlogger import jsonlogger


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """
    Custom JSON formatter with additional fields.
    """
    
    def __init__(
        self,
        service_name: str = "auth_service",
        environment: str = "production",
        *args,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.service_name = service_name
        self.environment = environment
    
    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict[str, Any]) -> None:
        """Add custom fields to the log record."""
        super().add_fields(log_record, record, message_dict)
        
        # Add service name and environment
        log_record["service"] = self.service_name
        log_record["environment"] = self.environment
        
        # Add process and thread info
        log_record["process"] = record.process
        log_record["thread"] = record.thread
        
        # Add timestamp if not present
        if not log_record.get("timestamp"):
            log_record["timestamp"] = self.formatTime(record)


def setup_logging(
    service_name: str = "auth_service",
    log_file: Optional[str] = None,
    log_level: str = "INFO",
    json_logs: bool = True,
    environment: str = None
) -> None:
    """
    Configure structured JSON logging for production.
    
    Args:
        service_name: Name of the service
        log_file: Path to log file (None for stdout)
        log_level: Logging level
        json_logs: Whether to use JSON format
        environment: Environment name (production, staging, development)
    """
    # Determine environment
    if environment is None:
        environment = os.getenv("ENVIRONMENT", "development")
    
    # Get numeric log level
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {log_level}")
    
    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create handlers
    handlers = []
    
    # Console handler always included
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    handlers.append(console_handler)
    
    # File handler if specified
    if log_file:
        # Create directory if needed
        log_path = Path(log_file)
        if not log_path.parent.exists():
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(numeric_level)
        handlers.append(file_handler)
    
    # Configure formatter
    if json_logs:
        json_format = "%(timestamp)s %(levelname)s %(name)s %(message)s"
        formatter = CustomJsonFormatter(
            service_name=service_name,
            environment=environment,
            fmt=json_format
        )
    else:
        # Traditional format for development
        text_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        formatter = logging.Formatter(text_format)
    
    # Apply formatter to all handlers
    for handler in handlers:
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)
    
    # Set logging for some noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("watchdog.observers").setLevel(logging.WARNING)


if __name__ == "__main__":
    # Example usage
    setup_logging(
        service_name="auth_service",
        log_file="/logs/auth_service.log",
        log_level="INFO",
        json_logs=True
    )
    
    logger = logging.getLogger("auth_service")
    logger.info("Logging configured", extra={"user_id": "example"})
    logger.error("An error occurred", extra={"error_code": 500})