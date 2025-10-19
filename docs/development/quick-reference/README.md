# Quick Reference Guides

Fast command references and cheat sheets for common development and operational tasks.

---

## 📚 Available Guides

### Historical Data Loader
- **[HISTORICAL_LOADER_QUICKREF.md](./HISTORICAL_LOADER_QUICKREF.md)** - Quick reference for historical data loading
  - Command syntax
  - Common use cases
  - Troubleshooting tips

---

## 🚀 Common Commands

### Docker Operations
```bash
# Start all services
docker-compose up -d

# Restart specific service
docker-compose restart data_service

# View logs
docker logs -f data_service

# Check service status
docker-compose ps

# Stop all services
docker-compose down
```

### Data Loading
```bash
# Load historical data for specific date
docker exec data_service python /app/services/data_service/load/historical_batch_loader.py --date 2025-10-17

# Start live data streaming
docker exec data_service python /app/services/data_service/load/realtime_stream_processor.py

# Run scheduler immediately
docker exec data_service python /app/services/data_service/load/scheduler.py --run-now
```

### Database Operations
```bash
# Connect to TimescaleDB
docker exec -it timescaledb psql -U trader -d trading

# Check tick data count
docker exec timescaledb psql -U trader -d trading -c "SELECT COUNT(*) FROM tick_data;"

# Check OHLCV data by interval
docker exec timescaledb psql -U trader -d trading -c "SELECT interval, COUNT(*) FROM ohlcv_data GROUP BY interval;"

# Get latest data timestamp
docker exec timescaledb psql -U trader -d trading -c "SELECT MAX(timestamp) FROM tick_data;"
```

### MinIO Operations
```bash
# List buckets
docker exec minio mc ls minio/

# List historical data
docker exec minio mc ls minio/market-data/historical/

# Check specific instrument
docker exec minio mc ls minio/market-data/historical/408065/
```

### Monitoring
```bash
# Monitor heartbeat
monitor_heartbeat.bat

# Watch live logs
docker logs -f data_service | findstr "HEARTBEAT Market"

# Check health endpoint
curl http://localhost:8080/api/v1/health
```

---

## 🔍 Debugging Commands

### Service Health
```bash
# Check all services
for service in auth_service data_service strategy_service execution_service risk_service monitoring_service; do
    echo "=== $service ==="
    docker logs $service --tail 5
    echo
done
```

### Network Diagnostics
```bash
# Test connectivity
docker exec data_service ping timescaledb
docker exec data_service ping kafka
docker exec data_service ping minio

# Check DNS
docker exec data_service nslookup timescaledb
```

### Storage Diagnostics
```bash
# Check Docker volumes
docker volume ls

# Inspect volume
docker volume inspect algotrading_v1_postgres_data

# Check disk usage
docker system df
```

---

## 📊 Useful SQL Queries

### TimescaleDB

```sql
-- Count ticks by instrument
SELECT 
    instrument_token,
    COUNT(*) as tick_count,
    MAX(timestamp) as latest_tick
FROM tick_data
GROUP BY instrument_token
ORDER BY tick_count DESC;

-- OHLCV data summary
SELECT 
    interval,
    COUNT(*) as candle_count,
    MIN(timestamp) as first_candle,
    MAX(timestamp) as latest_candle
FROM ohlcv_data
GROUP BY interval
ORDER BY interval;

-- Recent ticks
SELECT * FROM tick_data
ORDER BY timestamp DESC
LIMIT 10;

-- Data volume by day
SELECT 
    DATE(timestamp) as date,
    COUNT(*) as tick_count
FROM tick_data
GROUP BY DATE(timestamp)
ORDER BY date DESC;
```

---

## 🔧 Configuration Shortcuts

### Environment Variables
```bash
# View current config
docker exec data_service env | grep -E "LIVE_DATA|HISTORICAL"

# Check logging level
docker exec data_service env | grep LOG_LEVEL

# View Kafka config
docker exec data_service env | grep KAFKA
```

### Quick Edits
```bash
# Edit secrets (be careful!)
nano config/secrets.env

# Edit main config
nano config/config.yaml

# Reload service after config change
docker-compose restart data_service
```

---

## 🎯 Common Workflows

### Morning Startup Routine
```bash
# 1. Check if services are running
docker-compose ps

# 2. If not, start them
docker-compose up -d

# 3. Wait for health
sleep 10

# 4. Check health endpoints
curl http://localhost:8080/api/v1/health

# 5. Monitor for issues
docker logs data_service --tail 50
```

### Data Verification
```bash
# 1. Check database has data
docker exec timescaledb psql -U trader -d trading -c "SELECT COUNT(*) FROM tick_data;"

# 2. Check MinIO has files
docker exec minio mc ls minio/market-data/historical/

# 3. Verify recent data
docker exec timescaledb psql -U trader -d trading -c "SELECT MAX(timestamp) FROM tick_data;"

# 4. Check heartbeat is active
docker logs data_service | findstr "HEARTBEAT" | tail -n 1
```

### Troubleshooting Workflow
```bash
# 1. Check service status
docker-compose ps

# 2. View recent logs
docker logs data_service --tail 100

# 3. Check errors
docker logs data_service | findstr "ERROR"

# 4. Test database connection
docker exec timescaledb pg_isready -U trader

# 5. Restart if needed
docker-compose restart data_service

# 6. Monitor recovery
docker logs -f data_service
```

---

## 📖 More Resources

- [Development Guide](../README.md)
- [Operations Guide](../../operations/)
- [Troubleshooting](../../operations/troubleshooting/)
- [Service Documentation](../../services/)
