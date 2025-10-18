# Logging System: Future Improvements

This document outlines the current state of the logging system and suggests future improvements.

## Current State

- ✅ Centralized logger implementation in `core/utils/logger.py`
- ✅ Enhanced features: JSON formatting, IST timezone, log rotation
- ✅ Configuration via YAML files or environment variables
- ✅ Adopted by main service files across the platform

## Improvement Opportunities

### 1. Standardize Logger Usage

Several files still import and use Python's standard logging module directly. These should be refactored to use the centralized logger:

- `services/auth_service/idempotency.py`
- `services/auth_service/retry_utils.py`
- `services/auth_service/utils/retry.py`
- `services/auth_service/utils/idempotency.py`
- `services/auth_service/token_security.py`
- `services/auth_service/api/middlewares/logging.py`
- `services/data_service/extraction/live_data.py`
- `services/data_service/extraction/historical_data.py`
- `core/messaging/redis_client.py`

### 2. Add Context Information

Enhance the logger to support context information that can be added to all log entries:

```python
# Example usage
with logger.context(request_id=123, user="admin"):
    logger.info("Processing request")  # Will include request_id and user
```

### 3. Performance Metrics

Add support for performance metrics in logs:

```python
# Example usage
with logger.measure_time("database_query"):
    result = db.execute_query()
# Logs execution time automatically
```

### 4. Structured Data Support

Improve structured data logging to make it easier to include complex objects:

```python
# Example usage
logger.info("Order created", extra={"order": order.to_dict()})
```

### 5. Log Aggregation Integration

Add integration with log aggregation tools:

- Loki
- Elasticsearch
- Fluentd/Fluent Bit

### 6. Request Tracing

Add request tracing support:

```python
# Example usage
logger.set_trace_id(request.headers.get("X-Trace-Id"))
```

## Implementation Plan

1. Create a ticket to refactor each file listed in point 1
2. Implement context support (point 2) in core logger
3. Add performance metrics support (point 3)
4. Enhance structured data support (point 4)
5. Integrate with log aggregation (point 5)
6. Add request tracing (point 6)

## Migration Guide

When refactoring existing code that uses standard logging:

1. Replace direct logging imports with core logger import:
   ```python
   # From
   import logging
   logger = logging.getLogger("module_name")
   
   # To
   from core.utils.logger import get_logger
   logger = get_logger("module_name")
   ```

2. No changes needed to logging calls (`logger.info()`, `logger.error()`, etc.)