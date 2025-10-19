# Heartbeat Monitoring Guide
**AlgoTrading Platform - Data Flow Health Monitoring**

## Overview

The platform includes comprehensive heartbeat logging to monitor data flow in real-time. Heartbeat messages are logged at regular intervals to ensure you can verify everything is working correctly.

## 💓 Heartbeat Features

### 1. Live Data Processor Heartbeat

**Frequency**: Every 60 seconds (configurable via `HEARTBEAT_INTERVAL` env variable)

**Log Format**:
```
💓 HEARTBEAT | Uptime: 15m | Connected: 🟢 | Ticks: 1,234 | Stored: 1,234 | Candles: 45 | Errors: 0 | Last Tick: 🟢 2s ago
```

**Status Indicators**:
- 🟢 **Green**: Everything healthy (last tick < 30s ago)
- ⚠️  **Yellow Warning**: Last tick 30-60s ago
- 🔴 **Red Alert**: Last tick > 60s ago or no connection

**What it shows**:
- **Uptime**: How long the processor has been running
- **Connected**: WebSocket connection status
- **Ticks**: Total ticks received from WebSocket
- **Stored**: Total ticks stored to TimescaleDB
- **Candles**: Total candles generated (all intervals)
- **Errors**: Count of processing errors
- **Last Tick**: Time since last tick received

**Detailed Stats** (every 5 minutes):
```
================================================================================
📊 LIVE DATA PROCESSOR STATISTICS
================================================================================
   Uptime: 0h 15m 30s
   Connected: 🟢 YES
   Ticks Received: 3,450
   Ticks Stored: 3,450
   Candles Generated: 75
   Errors: 0
   Last Tick: 3s ago
   Tick Batch Size: 245
================================================================================
```

### 2. Historical Data Loader Heartbeat

**Frequency**: Every task completion (symbol + interval combination)

**Log Format**:
```
💓 PROGRESS | Task 5/45 (11.1%) | Symbol: NIFTY_50 | Interval: minute | Elapsed: 2m | ETA: 15m
```

**What it shows**:
- **Task Progress**: Current task number / total tasks
- **Percentage**: Completion percentage
- **Symbol**: Currently processing symbol
- **Interval**: Current interval being fetched
- **Elapsed**: Time since start
- **ETA**: Estimated time to completion

**Final Heartbeat**:
```
================================================================================
💓 FINAL HEARTBEAT - Load Complete
================================================================================
📊 Daily Load Summary for 2025-10-18
   Total Tasks: 45
   ✅ Completed: 42
   ⏭️  Skipped (existing): 3
   ❌ Failed: 0
   ⏱️  Duration: 18m 45s
   📈 Success Rate: 93.3%
================================================================================
```

### 3. Scheduler Heartbeat

**When Started**:
```
🚀 Starting Historical Data Scheduler...
   Schedule: Daily at 16:30 IST
   Next run: 2025-10-19 16:30:00+05:30
💓 Scheduler heartbeat active - waiting for schedule...
```

**When Job Runs**:
```
================================================================================
💓 HEARTBEAT - Starting scheduled historical data load
   Time: 2025-10-19 16:30:00 IST
================================================================================
```

**When Job Completes**:
```
================================================================================
💓 HEARTBEAT - Scheduled job completed successfully
   Duration: 18m 45s
   Completed at: 2025-10-19 16:48:45 IST
================================================================================
```

## 🔧 Configuration

### Customize Heartbeat Interval (Live Data)

**Environment Variable**:
```bash
# Set in .env or docker-compose.yml
HEARTBEAT_INTERVAL=60  # seconds (default)
```

**Examples**:
- `30` = Every 30 seconds (high frequency)
- `60` = Every minute (default, recommended)
- `300` = Every 5 minutes (low frequency)

**Update in docker-compose.yml**:
```yaml
data_service:
  environment:
    - HEARTBEAT_INTERVAL=60
```

## 📋 Monitoring Commands

### View Live Data Heartbeat

**Real-time logs**:
```bash
# View all logs
docker logs -f data_service

# Filter for heartbeat only
docker logs -f data_service | findstr "HEARTBEAT"

# Filter for heartbeat and errors
docker logs -f data_service | findstr /C:"HEARTBEAT" /C:"ERROR"
```

**PowerShell** (better filtering):
```powershell
# Live heartbeat monitoring
docker logs -f data_service 2>&1 | Select-String -Pattern "HEARTBEAT|ERROR|WARNING"

# Just heartbeats
docker logs -f data_service 2>&1 | Select-String -Pattern "💓"
```

### View Historical Loader Progress

```bash
# Run historical loader and watch progress
docker exec data_service python /app/services/data_service/load/historical_data.py --date 2025-10-18

# Monitor from another terminal
docker logs -f data_service | findstr "PROGRESS"
```

### Check Scheduler Status

```bash
# View scheduler logs
docker logs -f data_service | findstr "Scheduler"

# Check next scheduled run
docker exec data_service python -c "from services.data_service.load.scheduler import HistoricalDataScheduler; s = HistoricalDataScheduler(); print(f'Next run: {s.scheduler.get_jobs()[0].next_run_time}')"
```

## 📊 Log File Locations

All heartbeat logs are written to:
```
logs/data_service.log
```

**Viewing log file**:
```bash
# Windows
type logs\data_service.log | findstr "HEARTBEAT"

# View last 100 lines
powershell -Command "Get-Content logs\data_service.log -Tail 100"

# Follow log file (PowerShell)
powershell -Command "Get-Content logs\data_service.log -Wait -Tail 50"
```

## 🚨 Health Check Alerts

### Normal Operation (All Green)

```
💓 HEARTBEAT | Uptime: 120m | Connected: 🟢 | Ticks: 36,000 | Stored: 36,000 | Candles: 1,200 | Errors: 0 | Last Tick: 🟢 2s ago
```
✅ **Action**: None required

### Warning (Yellow)

```
💓 HEARTBEAT | Uptime: 125m | Connected: 🟢 | Ticks: 36,010 | Stored: 36,010 | Candles: 1,203 | Errors: 0 | Last Tick: ⚠️  45s ago
```
⚠️  **Action**: Monitor next heartbeat. If continues, check:
- Market hours (market may be closed)
- Network connectivity
- WebSocket connection logs

### Critical (Red)

```
💓 HEARTBEAT | Uptime: 130m | Connected: 🔴 | Ticks: 36,010 | Stored: 36,010 | Candles: 1,203 | Errors: 5 | Last Tick: 🔴 125s ago
```
🔴 **Action**: Immediate investigation required:
1. Check WebSocket disconnection logs
2. Verify auth token validity
3. Check network connectivity
4. Review error logs

### No Ticks Received

```
💓 HEARTBEAT | Uptime: 5m | Connected: 🟢 | Ticks: 0 | Stored: 0 | Candles: 0 | Errors: 0 | Last Tick: ⚠️  No ticks yet
```
⚠️  **Action**: 
- If market hours: Check subscription and symbols
- If outside market hours: Normal (9:15 AM - 3:30 PM IST weekdays)

## 🔍 Troubleshooting with Heartbeat Logs

### Scenario 1: Ticks Received but Not Stored

**Heartbeat shows**:
```
Ticks: 1,000 | Stored: 0
```

**Diagnosis**: Database connection issue

**Check**:
```bash
docker exec timescaledb pg_isready -U trader
docker logs data_service | findstr "Database"
```

### Scenario 2: Candles Not Generating

**Heartbeat shows**:
```
Ticks: 5,000 | Stored: 5,000 | Candles: 0
```

**Diagnosis**: Candle generation disabled or processor error

**Check**:
```bash
# Verify candle generation enabled
docker logs data_service | findstr "Candle generation"

# Check for candle processing errors
docker logs data_service | findstr "Error generating candles"
```

### Scenario 3: Frequent Disconnections

**Heartbeat shows**:
```
Connected: 🔴 (alternating with 🟢)
```

**Diagnosis**: Network instability or token expiry

**Check**:
```bash
# Check WebSocket connection logs
docker logs data_service | findstr "WebSocket"

# Check auth token
curl -H "X-Admin-API-Key: your_key" http://localhost:8018/admin/token
```

### Scenario 4: High Error Rate

**Heartbeat shows**:
```
Errors: 150 (and increasing)
```

**Diagnosis**: Data processing errors

**Check**:
```bash
# View all errors
docker logs data_service | findstr "ERROR"

# Count error types
docker logs data_service | findstr "ERROR" | findstr /C:"Database" /C:"Kafka" /C:"MinIO"
```

## 📈 Monitoring Best Practices

### 1. Regular Checks

**Daily**:
- Check heartbeat logs for any red/yellow indicators
- Verify tick counts are reasonable (1,000-10,000+ per hour during market hours)
- Confirm candle generation is active

**Weekly**:
- Review error counts and trends
- Check database storage growth
- Verify MinIO data partitions

### 2. Automated Monitoring

**Create monitoring script** (`monitor_heartbeat.bat`):
```batch
@echo off
echo Monitoring heartbeat (Ctrl+C to stop)
echo.
docker logs -f data_service | findstr "HEARTBEAT ERROR WARNING"
```

**Run in background**:
```bash
start monitor_heartbeat.bat
```

### 3. Alert Thresholds

Set up alerts (manual or automated) for:
- ❌ No heartbeat for > 5 minutes
- ⚠️  Error count > 100 in 1 hour
- ⚠️  No ticks during market hours for > 2 minutes
- ⚠️  Disconnection lasting > 1 minute

## 📝 Sample Monitoring Session

**Terminal 1 - Live Data Streaming**:
```bash
docker exec -it data_service python /app/services/data_service/load/live_data.py
```

**Terminal 2 - Heartbeat Monitor**:
```bash
docker logs -f data_service | findstr "💓"
```

**Expected Output (Terminal 2)**:
```
2025-10-19 15:30:00 | INFO | 💓 Heartbeat monitoring started (interval: 60s)
2025-10-19 15:31:00 | INFO | 💓 HEARTBEAT | Uptime: 1m | Connected: 🟢 | Ticks: 120 | Stored: 120 | Candles: 4 | Errors: 0 | Last Tick: 🟢 2s ago
2025-10-19 15:32:00 | INFO | 💓 HEARTBEAT | Uptime: 2m | Connected: 🟢 | Ticks: 240 | Stored: 240 | Candles: 8 | Errors: 0 | Last Tick: 🟢 1s ago
2025-10-19 15:33:00 | INFO | 💓 HEARTBEAT | Uptime: 3m | Connected: 🟢 | Ticks: 360 | Stored: 360 | Candles: 12 | Errors: 0 | Last Tick: 🟢 3s ago
```

## 🎯 Quick Reference

| Component | Heartbeat Interval | Log Pattern | Key Metrics |
|-----------|-------------------|-------------|-------------|
| **Live Data** | 60s (default) | `💓 HEARTBEAT \|` | Ticks, Stored, Candles, Errors |
| **Historical** | Per task | `💓 PROGRESS \|` | Task progress, ETA |
| **Scheduler** | On start/complete | `💓 HEARTBEAT -` | Duration, Success rate |

| Status | Indicator | Meaning | Action |
|--------|-----------|---------|--------|
| **Healthy** | 🟢 | All systems normal | None |
| **Warning** | ⚠️  | Degraded performance | Monitor |
| **Critical** | 🔴 | System failure | Investigate |

---

**Last Updated**: October 19, 2025  
**Version**: 1.0  
**Status**: ✅ Operational
