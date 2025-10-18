# Core Utilities Guide

**Centralized utilities for the AlgoTrading platform**

## 📁 Location

All core utilities are in `core/utils/`:

```
core/
├── __init__.py                    # Convenience exports
└── utils/
    ├── config_loader.py           # Simple YAML config loading
    ├── logger.py                  # Structured logging
    ├── metrics.py                 # Prometheus metrics
    ├── retry.py                   # Retry decorators
    └── time_utils.py              # Time/timezone utilities
```

## 🎯 Single Source of Truth

**✅ Use these files across ALL services:**

1. **`core/utils/logger.py`** - Logging (replaces all duplicate loggers)
2. **`core/utils/config_loader.py`** - Simple config loading

**❌ Removed duplicates:**
- ~~`common/logger.py`~~ (deleted)
- ~~`services/auth_service/core/utils/logger.py`~~ (deleted)

## 📖 Usage Guide

### Logging

#### Basic Usage

```python
# Recommended: Direct import
from core.utils.logger import get_logger, setup_logging

# Or convenience import
from core import get_logger, setup_logging

# Initialize logging (in main.py)
setup_logging(
    service_name="data_service",
    environment="production",
    log_level="INFO"
)

# Get logger for your module
logger = get_logger(__name__)

# Log messages
logger.info("Service started")
logger.debug("Processing data", extra={"count": 100})
logger.warning("High memory usage", extra={"usage": "85%"})
logger.error("Failed to connect", extra={"host": "localhost"})
```

#### With YAML Config

```python
# Use logging.yaml for advanced configuration
setup_logging(
    config_path="/app/config/logging.yaml",
    service_name="data_service"
)
```

#### Features

- ✅ **IST timezone** - All timestamps in Asia/Kolkata
- ✅ **JSON formatting** - Structured logs in production
- ✅ **File rotation** - 10MB max, 5 backups
- ✅ **Console output** - Human-readable in dev
- ✅ **Auto-initialization** - Lazy setup on first use
- ✅ **Logger caching** - Reuses logger instances

### Configuration Loading

#### Simple YAML Config (Recommended for most cases)

```python
# Direct import
from core.utils.config_loader import load_config

# Or convenience import
from core import load_config

# Auto-discovers config.yaml from current directory up
config = load_config()

# Or specify path
config = load_config("/app/config/config.yaml")

# Access config
db_host = config['database']['host']
kafka_brokers = config['kafka']['brokers']
```

#### Features

- ✅ **Auto-discovery** - Finds config.yaml walking up directories
- ✅ **Environment expansion** - Supports `${VAR}` placeholders
- ✅ **Simple dict** - Returns plain Python dictionary
- ✅ **No dependencies** - Just PyYAML

#### Example YAML

```yaml
# config/config.yaml
database:
  host: ${DB_HOST}
  port: 5432
  username: trader
  
kafka:
  enabled: true
  brokers: ${KAFKA_BROKERS}
```

### Pydantic Config (Advanced - When you need validation)

For services needing **type validation**, **auto-completion**, and **strict schemas**, use Pydantic:

```python
# services/data_service/config.py (keep for data service)
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

class DatabaseConfig(BaseModel):
    host: str = Field(default="localhost")
    port: int = Field(default=5432, ge=1, le=65535)
    
class Settings(BaseSettings):
    database: DatabaseConfig = DatabaseConfig()
    
    class Config:
        env_prefix = ""
        env_nested_delimiter = "__"

# Usage
from services.data_service.config import get_settings
settings = get_settings()
```

**When to use which:**

| Use Case | Use |
|----------|-----|
| Simple service config | `core.utils.config_loader` |
| Need validation | Pydantic config |
| Environment-only | `os.getenv()` |
| Complex nested config | Pydantic config |
| Quick prototyping | `core.utils.config_loader` |
| Production service | Either (based on complexity) |

## 🔄 Migration Guide

### From Old Logger

```python
# ❌ Old (deprecated - file deleted)
from common.logger import logger
logger.info("Message")

# ✅ New
from core.utils.logger import get_logger
logger = get_logger(__name__)
logger.info("Message")
```

### From Service-Specific Logger

```python
# ❌ Old (duplicate - file deleted)
from services.auth_service.core.utils.logger import get_logger

# ✅ New (same API!)
from core.utils.logger import get_logger
```

### From Manual Config Loading

```python
# ❌ Old (manual)
import yaml
with open("config.yaml") as f:
    config = yaml.safe_load(f)

# ✅ New (with env expansion)
from core.utils.config_loader import load_config
config = load_config()  # Auto-finds config.yaml
```

## 📝 Conventions

### Import Patterns

```python
# ✅ Preferred: Direct import from core.utils
from core.utils.logger import get_logger
from core.utils.config_loader import load_config

# ✅ Also acceptable: Convenience import from core
from core import get_logger, load_config

# ❌ Avoid: Creating local copies
# Don't copy logger.py to your service!
```

### Logger Naming

```python
# ✅ Good: Use __name__ for automatic module naming
logger = get_logger(__name__)
# Results in: "services.data_service.workers"

# ❌ Bad: Hardcoded names
logger = get_logger("my_logger")
```

### Config Access

```python
# ✅ Good: Load once at module level
from core.utils.config_loader import load_config
CONFIG = load_config()

def my_function():
    return CONFIG['database']['host']

# ❌ Bad: Loading in every function
def my_function():
    config = load_config()  # Wasteful!
    return config['database']['host']
```

## 🏗️ Architecture

### Why Centralized Utilities?

**Before (Duplicated):**
```
common/logger.py                          ❌ Duplicate
services/auth_service/core/utils/logger.py  ❌ Duplicate
core/utils/logger.py                      ❌ Not used

services/data_service/config.py           ❌ Over-engineered
core/utils/config_loader.py               ❌ Not used
```

**After (Centralized):**
```
core/utils/logger.py                      ✅ Single source
core/utils/config_loader.py               ✅ Single source

services/data_service/config.py           ✅ Optional for validation
```

**Benefits:**
- ✅ **No duplication** - Single implementation
- ✅ **Easier maintenance** - Fix once, works everywhere
- ✅ **Consistent behavior** - Same logging across services
- ✅ **Import simplicity** - One import path
- ✅ **Smaller codebase** - Less code to maintain

### Service Integration

```
┌─────────────────────────────────────────┐
│         Auth Service                    │
│  from core.utils.logger import get_logger
│  logger = get_logger(__name__)          │
└─────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│         core/utils/logger.py            │
│  - setup_logging()                      │
│  - get_logger()                         │
│  - JSONFormatter                        │
└─────────────────────────────────────────┘
                  ▲
                  │
┌─────────────────────────────────────────┐
│         Data Service                    │
│  from core.utils.logger import get_logger
│  logger = get_logger(__name__)          │
└─────────────────────────────────────────┘
```

## 🧪 Testing

### Test with Mocked Logger

```python
import pytest
from unittest.mock import Mock, patch

@patch('core.utils.logger.get_logger')
def test_my_function(mock_get_logger):
    mock_logger = Mock()
    mock_get_logger.return_value = mock_logger
    
    # Your test
    my_function()
    
    # Assert logging
    mock_logger.info.assert_called_once()
```

### Test with Real Logger

```python
import pytest
from core.utils.logger import get_logger, setup_logging

@pytest.fixture(scope="session")
def logger():
    setup_logging(service_name="test", log_level="DEBUG")
    return get_logger("test")

def test_with_logger(logger):
    logger.info("Test message")
    # Logs will appear in test output
```

## 📚 Related Documentation

- [Logging Guide](../guides/logging/README.md) - Detailed logging documentation
- [Production Readiness](../architecture/PRODUCTION_READINESS.md) - Production config
- [Data Service Config](../../services/data_service/config.py) - Pydantic example

## ❓ FAQ

### Q: Should I use `config_loader.py` or Pydantic config?

**A:** Depends on your needs:
- **Simple service** → Use `config_loader.py`
- **Need type validation** → Use Pydantic
- **Quick prototype** → Use `config_loader.py`
- **Production with complex config** → Use Pydantic

### Q: Can I use both?

**A:** Yes! Load YAML with `config_loader`, then pass to Pydantic:

```python
from core.utils.config_loader import load_config
from pydantic import BaseModel

raw_config = load_config()
settings = Settings(**raw_config)
```

### Q: What happened to `common/logger.py`?

**A:** Deleted! It was a duplicate. Use `core.utils.logger` instead.

### Q: How do I add custom log formatters?

**A:** Extend the logger in your service, or modify `core/utils/logger.py` for platform-wide changes.

### Q: Can I use a different timezone?

**A:** Edit `IST = ZoneInfo("Asia/Kolkata")` in `core/utils/logger.py` to your timezone.

---

**Version**: 1.0.0  
**Last Updated**: October 18, 2025  
**Status**: ✅ Consolidated and standardized
