# Centralized Logging Guide

## Overview

This document outlines the standardized approach for logging across all services in the AlgoTrading platform. We use a centralized logging system from the `core` module to ensure consistent log formatting, centralized configuration, and proper log management.

## Key Benefits

- **Consistency**: All services use the same logging format and configuration
- **Centralized Management**: Logging configuration is managed in one place
- **Structured JSON Logs**: Supports structured JSON logs for better parsing
- **Timezone Support**: All logs use IST (Indian Standard Time)
- **Rotation**: Log files are automatically rotated to manage disk space

## How to Use the Core Logger

### Basic Usage

```python
# Import the core logger
from core.utils.logger import setup_logging, get_logger

# Configure logging
setup_logging(
    config_path="config/logging.yaml",  # Optional YAML config
    service_name="your_service_name"    # Used for log file naming
)

# Get a logger for your module
logger = get_logger("module_name")

# Use the logger
logger.info("This is an info message")
logger.warning("This is a warning")
logger.error("An error occurred")
logger.debug("Debug information")
logger.exception("Exception with traceback")
```

### Configuration Options

The `setup_logging` function accepts the following parameters:

- `config_path`: Path to YAML config file (recommended)
- `service_name`: Name of the service (used for log file naming)
- `log_file`: Custom path to log file (optional)
- `log_level`: Logging level (INFO, DEBUG, WARNING, ERROR)
- `json_logs`: Whether to use JSON format (defaults to true in production)
- `environment`: Environment name (production, staging, development)

### YAML Configuration

For most services, we recommend using the YAML configuration file which provides more control:

```yaml
# Sample logging.yaml
version: 1
disable_existing_loggers: false

formatters:
  standard:
    format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    datefmt: "%Y-%m-%d %H:%M:%S"
  json:
    class: core.utils.logger.JSONFormatter

handlers:
  console:
    class: logging.StreamHandler
    level: INFO
    formatter: standard
    stream: ext://sys.stdout
  file:
    class: logging.handlers.RotatingFileHandler
    level: INFO
    formatter: json
    filename: logs/service.log
    maxBytes: 10485760  # 10MB
    backupCount: 5

loggers:
  uvicorn:
    level: WARNING
  kafka:
    level: WARNING

root:
  level: INFO
  handlers: [console, file]
  propagate: no
```

## Importing in Services

### Recommended Import Pattern

To ensure consistent imports across services:

```python
# At the top of your main service file
import sys
from pathlib import Path

# Add parent directory to path to resolve imports
parent_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(parent_dir))

# Import core logger
from core.utils.logger import setup_logging, get_logger

# Configure logging
setup_logging(
    config_path="config/logging.yaml", 
    service_name="your_service_name"
)

# Get a logger for your service
logger = get_logger("your_service_name")
```

## Best Practices

1. **Always initialize logging early** in your application startup
2. **Use descriptive logger names** that represent the module or component
3. **Include context** in log messages to make them more useful
4. **Use appropriate log levels**:
   - `DEBUG`: Detailed information for troubleshooting
   - `INFO`: General information about application progress
   - `WARNING`: Something unexpected but not necessarily an error
   - `ERROR`: A more serious problem that prevents normal operation
   - `CRITICAL`: A very serious error that may prevent the application from running
5. **Include structured data** when possible, especially in JSON logs

## Troubleshooting

If you encounter import issues with the logger:

1. Make sure the core module is in your Python path
2. Ensure required dependencies are installed (PyYAML for YAML config)
3. Check for circular imports in your module structure
4. Use the fallback in common/logger.py if the core logger is unavailable

## Migration Guide

When migrating existing services to use the core logger:

1. Replace service-specific logger implementations with the core logger
2. Adjust log message format if needed
3. Update log level configuration
4. Test thoroughly to ensure log messages appear correctly