# Logging System Guides

Comprehensive documentation for the structured logging system used across the AlgoTrading platform.

## 📋 Contents

- [**logging_system.md**](logging_system.md) - Complete logging system overview
- [**logging_guide.md**](logging_guide.md) - How to use the logging system
- [**logging_standardization.md**](logging_standardization.md) - Logging standards and conventions
- [**logging_refactoring_completion.md**](logging_refactoring_completion.md) - Refactoring completion report
- [**logging_future_improvements.md**](logging_future_improvements.md) - Future improvements roadmap
- [**logger_migration_guide.md**](logger_migration_guide.md) - Migration guide for legacy code

## 📊 Logging Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Application Code                       │
│  ┌───────────────────────────────────────────────────────┐  │
│  │     from core.utils.logger import get_logger          │  │
│  │     logger = get_logger(__name__)                     │  │
│  │     logger.info("Message", extra={"key": "value"})    │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   core.utils.logger.py                      │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  - setup_logging()      # Initialize logging          │  │
│  │  - get_logger()         # Get logger instance         │  │
│  │  - log_error()          # Enhanced error logging      │  │
│  │  - log_function_call()  # Decorator for tracing       │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  Logging Configuration                      │
│                  (config/logging.yaml)                      │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  - Formatters (JSON, Console)                         │  │
│  │  - Handlers (File, Console, Rotating)                 │  │
│  │  - Log Levels (DEBUG, INFO, WARNING, ERROR)           │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                 ┌────────────┴────────────┐
                 ▼                         ▼
┌──────────────────────────┐  ┌──────────────────────────┐
│   File Logs              │  │   Console Output         │
│   (logs/*.log)           │  │   (stdout/stderr)        │
│   - Rotating daily       │  │   - Human-readable       │
│   - JSON format          │  │   - Color-coded          │
│   - Structured data      │  │   - Development mode     │
└──────────────────────────┘  └──────────────────────────┘
```

## 🎯 Quick Start

### Basic Usage

```python
from core.utils.logger import get_logger

# Get logger for your module
logger = get_logger(__name__)

# Log messages
logger.info("Service started")
logger.debug("Processing data", extra={"count": 100})
logger.warning("High memory usage", extra={"usage": "85%"})
logger.error("Failed to connect", extra={"host": "localhost"})
```

### With Context

```python
# Add context to all log messages
logger.info("Processing order", extra={
    "order_id": 12345,
    "symbol": "RELIANCE",
    "quantity": 100,
    "price": 1416.80
})
```

### Error Logging

```python
from core.utils.logger import log_error

try:
    # Your code
    pass
except Exception as e:
    log_error(logger, e, {"operation": "fetch_data"})
```

### Function Tracing

```python
from core.utils.logger import log_function_call

@log_function_call
def process_data(data):
    # Your code
    return result
```

For detailed usage, see [logging_guide.md](logging_guide.md)

## 📐 Logging Standards

### Log Levels

- **DEBUG**: Detailed information for diagnosing issues
- **INFO**: General informational messages
- **WARNING**: Warning messages for potentially harmful situations
- **ERROR**: Error events that might still allow continued execution
- **CRITICAL**: Severe errors causing application failure

### Message Format

```python
# ✅ Good - Clear, actionable message with context
logger.info("User logged in successfully", extra={
    "user_id": "XWX042",
    "ip_address": "192.168.1.1",
    "session_id": "abc123"
})

# ❌ Bad - Vague message without context
logger.info("Login success")
```

### Structured Logging

Always use the `extra` parameter for structured data:

```python
# ✅ Good - Structured data in extra
logger.error("Order placement failed", extra={
    "order_id": 12345,
    "error_code": "INSUFFICIENT_FUNDS",
    "account_balance": 5000.00,
    "order_value": 7000.00
})

# ❌ Bad - Data embedded in message string
logger.error(f"Order {12345} failed: insufficient funds")
```

For complete standards, see [logging_standardization.md](logging_standardization.md)

## 🔧 Configuration

### Setup Logging

```python
from core.utils.logger import setup_logging

# In main.py or application entry point
setup_logging(
    config_path="/app/config/logging.yaml",
    service_name="data_service",
    environment="production"
)
```

### Log Rotation

Logs rotate automatically:
- **Daily rotation** at midnight
- **File naming**: `service_name_YYYY-MM-DD.log`
- **Retention**: 30 days
- **Compression**: Gzip for old logs

### Log Aggregation

In production, logs are collected by:
1. **Promtail** - Scrapes log files
2. **Loki** - Log aggregation
3. **Grafana** - Visualization and querying

## 🔍 Searching Logs

### In Development

```bash
# View real-time logs
tail -f logs/data_service.log

# Search for errors
grep "ERROR" logs/data_service.log

# Filter by context
grep "order_id.*12345" logs/data_service.log
```

### In Production

Use Grafana Loki:
```logql
{service="data_service"} |= "ERROR"
{service="data_service"} | json | order_id="12345"
```

## 📚 Migration Guide

### From Old Logger

```python
# Old way (deprecated - common/logger.py has been removed)
from common.logger import logger
logger.info("Message")

# New way - Use core utilities
from core.utils.logger import get_logger
logger = get_logger(__name__)
logger.info("Message")

# Or use convenience import
from core import get_logger
logger = get_logger(__name__)
logger.info("Message")
```

For complete migration guide, see [logger_migration_guide.md](logger_migration_guide.md)

## 🚀 Future Improvements

Planned enhancements:
- Distributed tracing with OpenTelemetry
- Log sampling for high-volume services
- Enhanced security audit logging
- Log-based alerting integration

See [logging_future_improvements.md](logging_future_improvements.md)

## 📖 Related Documentation

- [Production Readiness](../../architecture/PRODUCTION_READINESS.md) - Structured logging section
- [Data Service](../../services/data_service/README.md) - Service-specific logging

---

**Last Updated**: October 18, 2025
