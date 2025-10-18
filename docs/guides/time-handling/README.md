# Time Handling Guides

Documentation for timezone management and time handling strategies in the AlgoTrading platform.

## 📋 Contents

- [**time_handling.md**](time_handling.md) - Comprehensive time handling strategies
- [**time_handling_interview.md**](time_handling_interview.md) - In-depth Q&A on time handling

## ⏰ Time Zones Overview

The platform operates across multiple time zones:

```
┌─────────────────────────────────────────────────────────────┐
│                    Time Zone Hierarchy                      │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│  UTC (GMT)   │      │  IST (India) │      │   Local TZ   │
│              │      │              │      │              │
│  Database    │      │  Market      │      │  User        │
│  Storage     │      │  Hours       │      │  Display     │
└──────────────┘      └──────────────┘      └──────────────┘
      │                     │                     │
      │ Store in UTC        │ Market: 9:15-15:30  │ Convert for
      │ Always              │ IST                 │ Display
      └─────────────────────┴─────────────────────┘
```

## 🎯 Key Principles

### 1. Store in UTC
```python
from datetime import datetime, timezone

# ✅ Always store timestamps in UTC
timestamp = datetime.now(timezone.utc)

# Store in database
tick_data.timestamp = timestamp
```

### 2. Convert for Display
```python
import pytz

# Convert UTC to IST for display
ist = pytz.timezone('Asia/Kolkata')
local_time = utc_time.astimezone(ist)
```

### 3. Market Hours in IST
```python
# Indian market hours: 9:15 AM - 3:30 PM IST
MARKET_OPEN = time(9, 15)   # 9:15 AM IST
MARKET_CLOSE = time(15, 30)  # 3:30 PM IST
```

## 📊 Common Scenarios

### Scenario 1: Receiving WebSocket Tick
```python
from datetime import datetime, timezone

# Kite WebSocket sends IST timestamps
# Convert to UTC before storing
def process_tick(tick_data):
    ist = pytz.timezone('Asia/Kolkata')
    
    # Parse IST timestamp from Kite
    ist_time = datetime.fromisoformat(tick_data['timestamp'])
    ist_time = ist.localize(ist_time)
    
    # Convert to UTC for storage
    utc_time = ist_time.astimezone(timezone.utc)
    
    # Store in database
    await store_tick(utc_time, tick_data)
```

### Scenario 2: Querying Historical Data
```python
# Query data for specific IST date range
def get_data_for_date(date_str: str):
    # Parse date in IST
    ist = pytz.timezone('Asia/Kolkata')
    date = datetime.strptime(date_str, '%Y-%m-%d')
    
    # Market open in IST
    start_ist = ist.localize(datetime.combine(date, time(9, 15)))
    # Market close in IST
    end_ist = ist.localize(datetime.combine(date, time(15, 30)))
    
    # Convert to UTC for database query
    start_utc = start_ist.astimezone(timezone.utc)
    end_utc = end_ist.astimezone(timezone.utc)
    
    # Query database
    return query_ticks(start_utc, end_utc)
```

### Scenario 3: Displaying to User
```python
# API endpoint returning data to user
@app.get("/ticks")
def get_ticks():
    # Fetch from database (stored in UTC)
    ticks = fetch_ticks_from_db()
    
    # Convert timestamps to IST for display
    ist = pytz.timezone('Asia/Kolkata')
    for tick in ticks:
        tick['timestamp_ist'] = tick['timestamp'].astimezone(ist).isoformat()
    
    return ticks
```

## 🛡️ Best Practices

### DO ✅
- Store all timestamps in UTC
- Use timezone-aware datetime objects
- Convert to local time only for display
- Use ISO 8601 format for API responses
- Handle daylight saving time changes
- Validate timestamps before processing

### DON'T ❌
- Store timestamps in local time
- Use naive datetime objects
- Assume all times are in the same zone
- Hardcode timezone offsets
- Ignore timezone in calculations
- Mix aware and naive datetimes

## 🔧 Utility Functions

### Create Timezone-Aware Datetime
```python
from datetime import datetime, timezone
import pytz

def now_utc():
    """Get current time in UTC"""
    return datetime.now(timezone.utc)

def now_ist():
    """Get current time in IST"""
    ist = pytz.timezone('Asia/Kolkata')
    return datetime.now(ist)

def to_utc(dt, from_tz='Asia/Kolkata'):
    """Convert datetime to UTC"""
    tz = pytz.timezone(from_tz)
    if dt.tzinfo is None:
        dt = tz.localize(dt)
    return dt.astimezone(timezone.utc)

def to_ist(dt):
    """Convert datetime to IST"""
    ist = pytz.timezone('Asia/Kolkata')
    return dt.astimezone(ist)
```

### Market Hours Check
```python
from datetime import time
import pytz

def is_market_open(dt=None):
    """Check if Indian market is open"""
    if dt is None:
        dt = datetime.now(timezone.utc)
    
    # Convert to IST
    ist = pytz.timezone('Asia/Kolkata')
    ist_time = dt.astimezone(ist)
    
    # Check if weekday
    if ist_time.weekday() >= 5:  # Saturday = 5, Sunday = 6
        return False
    
    # Check market hours
    market_open = time(9, 15)
    market_close = time(15, 30)
    current_time = ist_time.time()
    
    return market_open <= current_time <= market_close
```

## 📚 Related Documentation

- [Time Handling Deep Dive](time_handling.md) - Detailed strategies
- [Time Handling Q&A](time_handling_interview.md) - Common questions
- [Data Service](../../services/data_service/README.md) - Time handling in practice

## 🐛 Common Issues

### Issue: Wrong timestamps in database
**Cause**: Storing local time instead of UTC  
**Solution**: Always convert to UTC before storing

### Issue: Off-by-one-day errors
**Cause**: Not handling timezone conversion properly  
**Solution**: Use timezone-aware datetimes throughout

### Issue: Market hours check failing
**Cause**: Checking in wrong timezone  
**Solution**: Always convert to IST before checking market hours

---

**Last Updated**: October 18, 2025
