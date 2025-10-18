# Time Handling Best Practices

## Overview

This document outlines best practices for handling time and dates in the AlgoTrading platform.

## Core Principles

1. **Use UTC for all stored timestamps**
2. **Use timezone-aware datetimes for all operations**
3. **Use ISO 8601 format for string representations of dates**
4. **Use the utility functions in `core.utils.time_utils` for all time operations**

## Time Utility Functions

The platform provides several utility functions in `core.utils.time_utils`:

### Basic Functions

- `utc_now()`: Get current UTC time with timezone information
- `timestamp_ms()`: Get current time as milliseconds timestamp
- `timestamp_s()`: Get current time as seconds timestamp

### Formatting Functions

- `format_iso(dt)`: Format a datetime object to ISO 8601 format
- `parse_datetime(dt_str)`: Parse a datetime string in various formats

### Conversion Functions

- `datetime_to_timestamp(dt)`: Convert datetime to Unix timestamp (seconds)
- `timestamp_to_datetime(timestamp)`: Convert Unix timestamp to datetime

## Examples

### Getting Current Time

```python
from core.utils.time_utils import utc_now

# Get current time in UTC
now = utc_now()
```

### Storing Time in Database

```python
from core.utils.time_utils import utc_now

# Store current time in database
record.created_at = utc_now()
```

### Comparing Times

```python
from core.utils.time_utils import utc_now

# Compare with database time (which might be timezone-naive)
now = utc_now().replace(tzinfo=None)
if record.expiry_time > now:
    # Token is still valid
```

### Formatting for UI

```python
from core.utils.time_utils import format_iso

# Format for UI display
iso_date = format_iso(record.created_at)
```

## Common Pitfalls

### Mixing Naive and Aware Datetimes

SQLAlchemy may store datetimes as timezone-naive. When comparing with timezone-aware datetimes, ensure consistency:

```python
# Correct way to compare naive database datetime with current time
from core.utils.time_utils import utc_now
now = utc_now().replace(tzinfo=None)  # Remove timezone for comparison
if db_record.expiry_time > now:
    # Valid comparison
```

### Using time.time() Directly

Avoid using `time.time()` directly. Instead, use:

```python
# Instead of time.time()
from core.utils.time_utils import timestamp_s
current_timestamp = timestamp_s()
```

### Inconsistent String Formats

Always use ISO 8601 format for string representations:

```python
# Good
from core.utils.time_utils import format_iso
iso_date = format_iso(record.created_at)  # '2025-10-18T15:30:45.123456+00:00'

# Avoid
str_date = record.created_at.strftime("%m/%d/%Y")  # Not recommended
```

## Migration Notes

If you're updating code to use the new time utilities:

1. Replace `datetime.utcnow()` with `utc_now()`
2. Replace `time.time()` with `timestamp_s()`
3. Use `format_iso()` for string representations
4. Use `parse_datetime()` to parse datetime strings

## Related Libraries

- [pytz](https://pypi.org/project/pytz/): Library for timezone calculations
- [pendulum](https://pendulum.eustace.io/): More intuitive datetime manipulation
- [arrow](https://arrow.readthedocs.io/): Human-friendly datetime manipulation