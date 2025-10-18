# Centralized Logging System

This document summarizes the centralized logging system implemented for the AlgoTrading platform.

## Overview

We've implemented a centralized, enhanced logging system to standardize logging across all services in the platform. The logger provides structured logging, IST timezone support, log rotation, and configuration options.

## Core Components

### Enhanced Logger (`core/utils/logger.py`)

The core logger implementation provides:

- JSON formatting for structured logs
- IST timezone support
- Log rotation with configurable file size and backup count
- Configuration via YAML files or environment variables
- Console and file output
- Singleton pattern for logger instances

## Usage Examples

### Basic Usage

```python
from core.utils.logger import get_logger

# Get a logger with the specified name
logger = get_logger("service_name")

# Log messages
logger.debug("Debug message")
logger.info("Info message")
logger.warning("Warning message")
logger.error("Error message")
logger.critical("Critical message")

# Include exception information
try:
    # Some code that may raise an exception
    1 / 0
except Exception as e:
    logger.exception("An error occurred: %s", str(e))
```

### Configuration

```python
from core.utils.logger import setup_logging

# Configure logging with a YAML file
setup_logging(config_path="config/logging.yaml")

# Configure logging with parameters
setup_logging(
    service_name="my_service",
    log_file="logs/my_service.log",
    log_level="DEBUG",
    json_logs=True,
    environment="production"
)
```

### Environment Variables

The logger supports the following environment variables:

- `SERVICE_NAME`: Name of the service
- `ENVIRONMENT`: Environment name (development, production, etc.)
- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `JSON_LOGS`: Whether to use JSON format (true/false)
- `LOG_DIR`: Directory for log files

## Configuration File Example

```yaml
# config/logging.yaml
version: 1
formatters:
  json:
    (): core.utils.logger.JSONFormatter
  standard:
    format: "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    datefmt: "%Y-%m-%d %H:%M:%S"

handlers:
  console:
    class: logging.StreamHandler
    level: INFO
    formatter: standard
    stream: ext://sys.stdout

  file:
    class: logging.handlers.RotatingFileHandler
    level: DEBUG
    formatter: json
    filename: logs/service.log
    maxBytes: 10485760  # 10MB
    backupCount: 5
    encoding: utf8

root:
  level: INFO
  handlers: [console, file]
  propagate: no

loggers:
  service_name:
    level: DEBUG
    handlers: [console, file]
    propagate: no
```

## Docker Integration

In your Dockerfile, ensure you create log directories:

```dockerfile
# Create log directories with proper permissions
RUN mkdir -p /app/logs && \
    chmod 755 /app/logs

# Set environment variables
ENV SERVICE_NAME=service_name
ENV LOG_DIR=/app/logs
```

## Migrated Services

The following services have been migrated to use the centralized logger:

- Auth Service
- Data Service
- Monitoring Service
- Risk Service
- Strategy Service
- Execution Service

## Benefits of Centralization

1. **Consistency**: All services use the same logging format and configuration
2. **Maintainability**: Single source of truth for logging implementation
3. **Enhanced Features**: All services benefit from improvements to the core logger
4. **Simplified Configuration**: Standardized configuration options across services