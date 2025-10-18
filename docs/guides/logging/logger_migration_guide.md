# Logger Migration Guide

This document provides instructions for migrating services to use the enhanced centralized logger in `core/utils/logger.py`.

## Background

We've enhanced the core logger (`core/utils/logger.py`) with advanced features to standardize logging across all services:

- YAML configuration file support
- JSON structured logging for production
- Environment-aware formatting
- Service name tagging
- Singleton pattern for consistent loggers
- Support for both console and file logging
- IST timezone support

## Migration Steps for Each Service

Follow these steps to update each service to use the enhanced logger:

### 1. Update Imports

Services that already import from `core.utils.logger` don't need import changes, but should update their usage:

```python
# Old usage
from core.utils.logger import get_logger
logger = get_logger("service_name")  # Missing setup_logging call

# New usage
from core.utils.logger import setup_logging, get_logger

# Configure logging (add this if missing)
setup_logging(
    config_path="config/logging.yaml",  # Optional: Use YAML config if available
    service_name="service_name",        # Required: Specify service name
    environment=os.getenv("ENVIRONMENT", "development")  # Optional: Environment context
)
logger = get_logger("service_name")
```

### 2. Remove Service-Specific Loggers

If your service has its own logger implementation, replace it with the core logger:

1. Identify files with logger implementations:
   - Look for `logging_config.py` or similar files
   - Search for custom `setup_logging` functions

2. Replace them with imports from `core.utils.logger`

### 3. Update Configuration

If your service uses a custom logging configuration:

1. Move any custom configuration to a YAML file in `config/logging.yaml`
2. Pass this path to `setup_logging`

### 4. Docker/Kubernetes Configuration

For containerized services:

1. Make sure environment variables are properly set:
   - `SERVICE_NAME`: Name of the service
   - `ENVIRONMENT`: "development", "staging", or "production"
   - `LOG_LEVEL`: Logging level ("INFO", "DEBUG", etc.)
   - `JSON_LOGS`: Set to "true" for JSON logging (recommended for production)

2. Ensure log directories are mounted correctly if using file logging

## Examples

### Basic Service Update

```python
import os
import sys
from pathlib import Path

# Add parent directory to path to resolve imports
parent_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(parent_dir))

# Import enhanced logger
from core.utils.logger import setup_logging, get_logger

# Configure logging
setup_logging(
    service_name="my_service",
    environment=os.getenv("ENVIRONMENT", "development"),
    json_logs=(os.getenv("ENVIRONMENT", "development") == "production")
)
logger = get_logger("my_service")

def main():
    logger.info("Starting My Service")
    # ...
```

### With YAML Configuration

```python
import os
import sys
from pathlib import Path

# Add parent directory to path to resolve imports
parent_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(parent_dir))

# Import enhanced logger
from core.utils.logger import setup_logging, get_logger

# Configure logging from YAML
setup_logging(
    config_path="config/logging.yaml",
    service_name="my_service"
)
logger = get_logger("my_service")

def main():
    logger.info("Starting My Service")
    # ...
```

## Verification

After migration, verify that:

1. Log messages appear in the expected format
2. Both console and file logging work as expected
3. Service name and environment are correctly displayed in logs
4. JSON formatting is applied in production

## Benefits

By standardizing on a single logger implementation, we gain:

1. Consistent logging format across all services
2. Centralized configuration management
3. Easier maintenance and updates
4. Better integration with monitoring tools