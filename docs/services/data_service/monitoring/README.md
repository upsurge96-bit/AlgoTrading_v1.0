# Data Service Monitoring

Monitoring guides and documentation for the data service.

---

## 📊 Monitoring Features

### Heartbeat Monitoring
- **[HEARTBEAT_MONITORING.md](./HEARTBEAT_MONITORING.md)** - Comprehensive heartbeat guide
  - Real-time data flow monitoring
  - Heartbeat intervals and configuration
  - Sample outputs and interpretation
  - Monitoring commands

### Market Status Logging
- **[MARKET_STATUS_LOGGING.md](./MARKET_STATUS_LOGGING.md)** - Market status awareness
  - Automatic market hours detection
  - Context-aware logging
  - Connection status with market state
  - Troubleshooting market-related issues

---

## 🎯 Quick Monitoring

### Real-Time Heartbeat
```bash
# Monitor heartbeat (Windows)
monitor_heartbeat.bat

# Monitor with Docker logs
docker logs -f data_service | findstr "HEARTBEAT"

# PowerShell (better formatting)
docker logs -f data_service 2>&1 | Select-String -Pattern "💓|Market|ERROR|WARNING"
```

### Heartbeat Interpretation

**Healthy System** (Market Open):
```
💓 HEARTBEAT | Uptime: 15m | Connected: 🟢 | Market: 🟢 OPEN | Ticks: 1,234 | Stored: 1,234 | Candles: 45 | Errors: 0 | Last Tick: 🟢 2s ago
```

**Healthy System** (Market Closed):
```
💓 HEARTBEAT | Uptime: 5m | Connected: 🟢 | Market: 🔴 CLOSED (Weekend) | Ticks: 0 | Stored: 0 | Candles: 0 | Errors: 0 | Last Tick: ⚠️ No ticks yet
ℹ️  WebSocket connected but market is Weekend (Sunday). Data will flow when market opens.
```

**Problem Detected**:
```
💓 HEARTBEAT | Uptime: 30m | Connected: 🔴 | Market: 🟢 OPEN | Ticks: 0 | Stored: 0 | Candles: 0 | Errors: 15 | Last Tick: 🔴 1800s ago
```
→ Market is open but not connected - investigate!

---

## 📈 Market Status Detection

The system automatically detects:
- **Market Hours**: Mon-Fri, 9:15 AM - 3:30 PM IST
- **Pre-Market**: Before 9:15 AM on trading days
- **After-Hours**: After 3:30 PM on trading days
- **Weekends**: Saturday and Sunday
- **Holidays**: (Manual configuration needed)

### Status Messages

| Scenario | Status Message |
|----------|----------------|
| Mon-Fri 9:15 AM - 3:30 PM | 🟢 Market OPEN (Market hours) |
| Mon-Fri before 9:15 AM | 🔴 Market CLOSED (Pre-market, opens at 09:15 AM) |
| Mon-Fri after 3:30 PM | 🔴 Market CLOSED (After-hours, closed at 03:30 PM) |
| Saturday | 🔴 Market CLOSED (Weekend (Saturday)) |
| Sunday | 🔴 Market CLOSED (Weekend (Sunday)) |

---

## 🔧 Configuration

### Heartbeat Interval
```bash
# In .env or docker-compose.yml
HEARTBEAT_INTERVAL=60  # seconds (default: 60)
```

### Live Data Symbols
```bash
# Instruments to monitor
LIVE_DATA_SYMBOLS=408065,884737,738561

# WebSocket mode
LIVE_DATA_MODE=full  # ltp, quote, or full

# Candle intervals
LIVE_DATA_INTERVALS=1m,5m,15m,1h,1d
```

---

## 📊 Monitoring Dashboards

### Basic Monitoring
```bash
# Service status
docker-compose ps

# Recent activity
docker logs data_service --tail 50

# Errors only
docker logs data_service | findstr "ERROR"
```

### Advanced Monitoring
```bash
# Real-time tick count
watch -n 5 'docker exec timescaledb psql -U trader -d trading -c "SELECT COUNT(*) FROM tick_data;"'

# Data flow rate (Windows - PowerShell)
while ($true) {
    $count = docker exec timescaledb psql -U trader -d trading -t -c "SELECT COUNT(*) FROM tick_data;"
    Write-Host "Ticks: $count - $(Get-Date)"
    Start-Sleep -Seconds 5
}
```

---

## 🚨 Alerts & Notifications

### Critical Conditions

**Alert if**:
- ❌ Market is OPEN but Connected: 🔴
- ❌ Market is OPEN but Ticks: 0 for >5 minutes
- ❌ Errors > 10 in last heartbeat period
- ❌ Last Tick > 300 seconds ago during market hours

**Normal conditions**:
- ✅ Market is CLOSED and Ticks: 0 (expected)
- ✅ Market is OPEN and Connected: 🟢 and Ticks > 0
- ✅ WebSocket reconnecting during connection issues

---

## 📈 Performance Metrics

### Key Metrics to Track

| Metric | Source | Healthy Range |
|--------|--------|---------------|
| Tick Ingestion Rate | Heartbeat | >100 ticks/min (market hours) |
| Storage Lag | Ticks vs Stored | <1% difference |
| Candle Generation | Heartbeat | Proportional to ticks |
| Error Rate | Heartbeat | <1% of ticks |
| Connection Uptime | Heartbeat | >99% during market hours |
| Last Tick Age | Heartbeat | <30 seconds (market hours) |

### Sample Monitoring Query
```sql
-- Real-time performance
SELECT 
    COUNT(*) as total_ticks,
    COUNT(*) FILTER (WHERE timestamp > NOW() - INTERVAL '1 minute') as last_minute,
    MAX(timestamp) as latest_tick,
    EXTRACT(EPOCH FROM (NOW() - MAX(timestamp))) as seconds_since_last
FROM tick_data;
```

---

## 🔍 Troubleshooting

### No Heartbeat Logs
**Cause**: Service not running or heartbeat disabled

**Fix**:
```bash
# Check service status
docker-compose ps

# Restart service
docker-compose restart data_service

# Enable heartbeat (if disabled)
# Set HEARTBEAT_INTERVAL > 0
```

### Market Shows Open But No Data
**Cause**: Connection issue, token expired, or subscription problem

**Checks**:
```bash
# 1. Verify WebSocket connected
docker logs data_service | findstr "WebSocket CONNECTED"

# 2. Check token valid
curl http://localhost:8018/admin/token -H "X-Admin-API-Key: your-key"

# 3. Verify subscription
docker logs data_service | findstr "Subscribed"
```

### High Error Rate
**Cause**: Network issues, API rate limiting, or data validation errors

**Actions**:
```bash
# 1. Check error logs
docker logs data_service | findstr "ERROR" | tail -n 20

# 2. Monitor errors in real-time
docker logs -f data_service | findstr "ERROR"

# 3. Check network
docker exec data_service ping ws.kite.trade
```

---

## 📚 Related Documentation

- [Data Service](../README.md) - Main service documentation
- [Troubleshooting](../../../operations/troubleshooting/) - Problem resolution
- [Architecture](../../../architecture/) - System design
- [Quick Reference](../../../development/quick-reference/) - Common commands
