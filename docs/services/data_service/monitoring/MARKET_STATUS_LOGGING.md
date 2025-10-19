# Market Status Logging - Feature Documentation

**Created**: October 19, 2025  
**Status**: ✅ **IMPLEMENTED AND ACTIVE**

---

## 🎯 Overview

The data service now includes **intelligent market status awareness** in all logging. The logger automatically detects whether the Indian stock market is open or closed and provides contextual messages explaining why data may or may not be flowing.

---

## ✨ Key Features

### 1. **Market Hours Detection**

The system automatically checks:
- ✅ **Current day** (Monday-Friday = trading days, Saturday-Sunday = weekend)
- ✅ **Current time** (9:15 AM - 3:30 PM IST = market hours)
- ✅ **Pre-market** (before 9:15 AM)
- ✅ **After-hours** (after 3:30 PM)
- ✅ **Weekends** (Saturday/Sunday)

### 2. **Contextual Logging**

**When WebSocket Connects**:
```
📊 🔴 Market CLOSED (Weekend (Sunday))
✅ Connected to Kite WebSocket
ℹ️  WebSocket connected, but market is Weekend (Sunday).
ℹ️  Data will flow when market opens (Mon-Fri 9:15 AM - 3:30 PM IST).
```

**When Market is Open**:
```
📊 🟢 Market OPEN (Market hours (9:15 AM - 3:30 PM))
✅ Connected to Kite WebSocket
```

### 3. **Heartbeat with Market Status**

Every 60 seconds (configurable), the heartbeat log includes market status:

**Market Closed**:
```
💓 HEARTBEAT | 
  Uptime: 5m | 
  Connected: 🟢 | 
  Market: 🔴 Market CLOSED (Weekend (Sunday)) | 
  Ticks: 0 | 
  Stored: 0 | 
  Candles: 0 | 
  Errors: 0 | 
  Last Tick: ⚠️ No ticks yet

ℹ️  WebSocket connected but market is Weekend (Sunday). 
    Data will flow when market opens.
```

**Market Open**:
```
💓 HEARTBEAT | 
  Uptime: 15m | 
  Connected: 🟢 | 
  Market: 🟢 Market OPEN (Market hours (9:15 AM - 3:30 PM)) | 
  Ticks: 1,234 | 
  Stored: 1,234 | 
  Candles: 45 | 
  Errors: 0 | 
  Last Tick: 🟢 2s ago
```

---

## 🔧 Implementation Details

### Files Modified

1. **`services/data_service/load/live_data.py`**
   - Added `is_market_open()` function
   - Added `get_market_status_message()` function
   - Updated `on_connect()` callback with market status
   - Updated `_heartbeat_loop()` with market status in logs
   - Updated `start()` method with initial market status

2. **`services/data_service/extraction/live_data.py`**
   - Added same market status detection functions
   - Updated `connect()` method with market status logging
   - Added contextual messages when connecting outside market hours

### Market Detection Logic

```python
def is_market_open() -> tuple[bool, str]:
    """
    Check if Indian stock market is open
    
    Returns:
        tuple: (is_open: bool, reason: str)
    """
    now_ist = datetime.now(IST)
    current_day = now_ist.weekday()  # 0=Monday, 6=Sunday
    current_time = now_ist.time()
    
    # Market hours: Monday-Friday, 9:15 AM - 3:30 PM IST
    MARKET_OPEN = time(9, 15)
    MARKET_CLOSE = time(15, 30)
    
    # Check if weekend
    if current_day >= 5:  # Saturday (5) or Sunday (6)
        day_name = now_ist.strftime("%A")
        return False, f"Weekend ({day_name})"
    
    # Check if during market hours
    if current_time < MARKET_OPEN:
        return False, f"Pre-market (opens at 09:15 AM)"
    elif current_time > MARKET_CLOSE:
        return False, f"After-hours (closed at 03:30 PM)"
    else:
        return True, "Market hours (9:15 AM - 3:30 PM)"
```

---

## 📊 Market Status Messages

### Status Types

| Scenario | Status | Reason Message |
|----------|--------|----------------|
| **Monday-Friday, 9:15 AM - 3:30 PM** | 🟢 OPEN | "Market hours (9:15 AM - 3:30 PM)" |
| **Monday-Friday, before 9:15 AM** | 🔴 CLOSED | "Pre-market (opens at 09:15 AM)" |
| **Monday-Friday, after 3:30 PM** | 🔴 CLOSED | "After-hours (closed at 03:30 PM)" |
| **Saturday** | 🔴 CLOSED | "Weekend (Saturday)" |
| **Sunday** | 🔴 CLOSED | "Weekend (Sunday)" |

### Log Levels

- **INFO**: Market status at connection and in heartbeat
- **INFO**: Contextual messages explaining why no data (when connected but market closed)
- **WARNING/ERROR**: Connection failures (independent of market status)

---

## 🎯 User Benefits

### 1. **Clear Understanding**

Users can immediately see:
- ✅ Is the WebSocket connected?
- ✅ Is the market open?
- ✅ Why isn't data flowing?

**Example**:
```
Connected: 🟢 | Market: 🔴 CLOSED (Weekend)
→ User knows: "System is healthy, just waiting for Monday"
```

### 2. **No More Confusion**

**Before** (without market status):
```
❌ Connect failed: HTTP 403
❌ Connect failed: HTTP 403
❌ Connect failed: HTTP 403
→ User thinks: "Something is broken!"
```

**After** (with market status):
```
📊 🔴 Market CLOSED (Weekend (Sunday))
✅ Connected to Kite WebSocket
ℹ️  WebSocket connected, but market is Weekend (Sunday).
ℹ️  Data will flow when market opens.
→ User knows: "Everything is working, market just closed"
```

### 3. **Proactive Monitoring**

Heartbeat shows market status every 60 seconds:
- If **connected + market open + no ticks** → Real problem!
- If **connected + market closed + no ticks** → Expected behavior

---

## 🔍 Monitoring Examples

### Monitor Real-Time Logs

```bash
# Watch heartbeat with market status
docker logs -f data_service | findstr "HEARTBEAT Market"

# PowerShell (better filtering)
docker logs -f data_service 2>&1 | Select-String -Pattern "💓|Market|ℹ️"

# Using monitor_heartbeat.bat
monitor_heartbeat.bat
```

### Sample Output (Market Closed)

```
2025-10-19 05:24:32 | INFO | 📊 🔴 Market CLOSED (Weekend (Sunday))
2025-10-19 05:24:33 | INFO | ✅ Connected to Kite WebSocket
2025-10-19 05:24:33 | INFO | ℹ️  WebSocket connected, but market is Weekend (Sunday).
2025-10-19 05:24:33 | INFO | ℹ️  Data will flow when market opens (Mon-Fri 9:15 AM - 3:30 PM IST).
2025-10-19 05:25:33 | INFO | 💓 HEARTBEAT | Uptime: 1m | Connected: 🟢 | Market: 🔴 Market CLOSED (Weekend (Sunday)) | Ticks: 0 | ...
2025-10-19 05:25:33 | INFO | ℹ️  WebSocket connected but market is Weekend (Sunday). Data will flow when market opens.
```

### Sample Output (Market Open - Expected Monday)

```
2025-10-21 09:20:00 | INFO | 📊 🟢 Market OPEN (Market hours (9:15 AM - 3:30 PM))
2025-10-21 09:20:01 | INFO | ✅ Connected to Kite WebSocket
2025-10-21 09:20:05 | INFO | 📊 Processed 100 ticks | Stored: 100 | Candles: 5 | Errors: 0
2025-10-21 09:21:00 | INFO | 💓 HEARTBEAT | Uptime: 1m | Connected: 🟢 | Market: 🟢 Market OPEN (Market hours (9:15 AM - 3:30 PM)) | Ticks: 120 | Stored: 120 | Candles: 6 | Errors: 0 | Last Tick: 🟢 2s ago
```

---

## 🧪 Testing

### Test Market Closed (Current - Sunday)

```bash
# Restart service and check logs
docker-compose restart data_service
docker logs -f data_service | findstr "Market"
```

**Expected**:
- ✅ "Market CLOSED (Weekend (Sunday))"
- ✅ "WebSocket connected, but market is Weekend (Sunday)"
- ✅ Heartbeat shows market closed status

### Test Market Open (Monday 9:15 AM+)

**Expected**:
- ✅ "Market OPEN (Market hours)"
- ✅ Ticks start flowing
- ✅ Heartbeat shows active data flow

---

## 📋 Configuration

### Heartbeat Interval

```bash
# In .env or config
HEARTBEAT_INTERVAL=60  # seconds (default: 60)
```

### Market Hours

Hardcoded in `is_market_open()` function:
- **Days**: Monday (0) to Friday (4)
- **Open**: 9:15 AM IST
- **Close**: 3:30 PM IST

**To change**: Edit the `is_market_open()` function in both:
- `services/data_service/load/live_data.py`
- `services/data_service/extraction/live_data.py`

---

## 🚀 Next Steps

### What Happens Monday?

**Before Market Opens (9:00 AM)**:
```
Market: 🔴 CLOSED (Pre-market (opens at 09:15 AM))
→ WebSocket connected, waiting for market
```

**At Market Open (9:15 AM)**:
```
Market: 🟢 OPEN (Market hours (9:15 AM - 3:30 PM))
→ Ticks start flowing automatically
→ Heartbeat shows active data
```

**After Market Closes (3:30 PM)**:
```
Market: 🔴 CLOSED (After-hours (closed at 03:30 PM))
→ Tick flow stops
→ Heartbeat shows no new ticks (expected)
```

### Action Required

**Monday, October 21 @ 9:00 AM**:
1. Service should already be running
2. WebSocket will be connected
3. At 9:15 AM, ticks will automatically start flowing
4. Monitor with: `monitor_heartbeat.bat`

**No manual intervention needed!** System will automatically:
- ✅ Detect market open
- ✅ Start receiving ticks
- ✅ Update heartbeat status
- ✅ Log all data flow

---

## 📊 Troubleshooting

### Q: Logs say "Market OPEN" but no ticks?

**Check**:
1. WebSocket connected? (`Connected: 🟢`)
2. Subscribed to instruments? (check startup logs)
3. Network issues? (check error logs)
4. Token valid? (check auth service)

**This is a REAL problem** - market is open but data not flowing.

### Q: Logs say "Market CLOSED" but no ticks?

**This is EXPECTED!** Market is closed, so no data.

**Check**: Is it actually market hours?
- Current day: Monday-Friday?
- Current time: 9:15 AM - 3:30 PM IST?

If yes and logs still say closed → Time zone issue (check server time).

### Q: Emojis look garbled in logs?

**Windows Command Prompt Issue**: Emojis may not render properly.

**Solution**:
- Use PowerShell instead: `docker logs -f data_service`
- Or use `monitor_heartbeat.bat` (formats output)
- Or check log files directly (UTF-8 encoded)

**The data is correct**, just display issue.

---

## ✅ Summary

| Feature | Status | Details |
|---------|--------|---------|
| **Market Detection** | ✅ Active | Detects day/time, determines open/closed |
| **Connection Logging** | ✅ Active | Shows market status when WebSocket connects |
| **Heartbeat Status** | ✅ Active | Every 60s with market status |
| **Contextual Messages** | ✅ Active | Explains why no data when market closed |
| **Timezone Handling** | ✅ Correct | Uses IST (Asia/Kolkata) |
| **Docker Integration** | ✅ Working | Rebuilt and running |

---

**Report Generated**: October 19, 2025 @ 05:24 AM IST (Sunday)  
**Next Market Open**: Monday, October 21, 2025 @ 9:15 AM IST  
**Current Status**: ✅ **WebSocket Connected, Market Closed (as expected)**  
**Action Required**: ⏰ **None - system ready for Monday**
