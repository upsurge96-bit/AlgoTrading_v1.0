"""Enhanced logging for Algo-Trading Platform services.

This module provides a centralized logging system with console and file output,
JSON formatting, and IST timezone support.
"""

import logging
import os
import json
import sys
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler
from zoneinfo import ZoneInfo

# Set IST timezone for logs
IST = ZoneInfo("Asia/Kolkata")

# Global tracking for initialization state and logger cache
_logging_initialized = False
_loggers = {}

class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record):
        """Format log records as JSON."""
        log_data = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "service": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_data)

    def formatTime(self, record, datefmt=None):
        """Format timestamps in IST timezone."""
        dt = datetime.fromtimestamp(record.created, IST)
        return dt.strftime(datefmt or "%Y-%m-%d %H:%M:%S")


def setup_logging(
    config_path=None,
    service_name=None,
    log_file=None,
    log_level=None,
    json_logs=None,
    environment=None
):
    """Configure logging for the application.
    
    Args:
        config_path: Path to YAML config file
        service_name: Name of the service
        log_file: Path to log file
        log_level: Logging level
        json_logs: Whether to use JSON format
        environment: Environment name
    """
    global _logging_initialized
    import logging  # Make sure logging is imported at function scope
    
    # Reset initialization state
    _logging_initialized = False
    
    # Try loading config from file first
    if config_path and Path(config_path).exists():
        try:
            import yaml
            import logging.config
            
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            logging.config.dictConfig(config)
            print(f"✅ Configured logging from {config_path}")
            _logging_initialized = True
            return
        except Exception as e:
            print(f"⚠️ Error loading logging config: {e}")
    
    # Get settings from environment or use defaults
    service_name = service_name or os.getenv("SERVICE_NAME", "algo_trading")
    environment = environment or os.getenv("ENVIRONMENT", "development")
    log_level = log_level or os.getenv("LOG_LEVEL", "INFO").upper()
    json_logs = json_logs if json_logs is not None else (
        environment == "production" or 
        os.getenv("JSON_LOGS", "").lower() == "true"
    )
    
    # Get numeric log level
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    
    # File handler
    if log_file is None:
        log_dir = os.getenv("LOG_DIR", "logs")
        log_file = os.path.join(log_dir, f"{service_name}.log")
    
    handlers = [console_handler]
    
    try:
        # Create directory if needed
        log_path = Path(log_file)
        if not log_path.parent.exists():
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
        # Use rotating file handler
        file_handler = RotatingFileHandler(
            log_file, 
            maxBytes=10_000_000,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(numeric_level)
        handlers.append(file_handler)
    except Exception as e:
        print(f"⚠️ Could not initialize file handler: {e}")
    
    # Configure formatter
    if json_logs:
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        formatter.converter = lambda *args: datetime.now(IST).timetuple()
    
    # Apply formatter to all handlers
    for handler in handlers:
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)
    
    # Set logging for some noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    
    _logging_initialized = True
    print(f"✅ Logging initialized: {service_name} ({environment})")


def get_logger(name="app", level=None):
    """Get a configured logger with the specified name.
    
    Args:
        name: Logger name
        level: Optional override for log level
        
    Returns:
        Logger instance
    """
    global _logging_initialized, _loggers
    
    # Initialize default logging if not already done
    if not _logging_initialized:
        setup_logging()
    
    # Return existing logger if cached
    if name in _loggers:
        logger = _loggers[name]
        if level is not None:
            numeric_level = getattr(logging, level.upper(), None)
            if isinstance(numeric_level, int):
                logger.setLevel(numeric_level)
        return logger
    
    # Create and cache new logger
    logger = logging.getLogger(name)
    
    # Set custom level if specified
    if level is not None:
        numeric_level = getattr(logging, level.upper(), None)
        if isinstance(numeric_level, int):
            logger.setLevel(numeric_level)
    
    # Cache the logger
    _loggers[name] = logger
    return logger
