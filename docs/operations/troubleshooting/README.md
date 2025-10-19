# Troubleshooting Documentation

Diagnostic guides and status reports for resolving operational issues.

---

## 🔍 Status Reports

### Data Extraction
- **[DATA_EXTRACTION_STATUS.md](./DATA_EXTRACTION_STATUS.md)** - Data extraction health check
  - Kite API connectivity
  - Historical data fetching
  - Live WebSocket status
  - Authentication validation

### Live Data Streaming
- **[LIVE_DATA_STATUS.md](./LIVE_DATA_STATUS.md)** - Live data streaming diagnostics
  - WebSocket connection status
  - Market hours detection
  - Tick flow analysis
  - Connection error explanations

### Database Health
- **[TIMESCALEDB_STATUS_REPORT.md](./TIMESCALEDB_STATUS_REPORT.md)** - Database status
  - Table statistics
  - Data volume metrics
  - Query performance
  - Hypertable health

---

## 🚨 Common Issues

### WebSocket HTTP 403 Errors

**Symptom**: Logs show `HTTP 403` when connecting to Kite WebSocket

**Cause**: Market is closed (weekend, holidays, outside trading hours)

**Solution**: This is expected! WebSocket only accepts connections during market hours (Mon-Fri 9:15 AM - 3:30 PM IST).

**Verification**:
```bash
# Check market status in logs
docker logs data_service | findstr "Market"
# Should show: "🔴 Market CLOSED (Weekend)" or similar
```

### No Data Flowing

**Symptom**: WebSocket connected but no ticks received

**Check**:
1. Is market open? (Mon-Fri 9:15 AM - 3:30 PM IST)
2. Are tokens valid? Check auth service
3. Are instruments subscribed? Check startup logs

**Debugging**:
```bash
# Check heartbeat
docker logs data_service | findstr "HEARTBEAT"

# Verify subscription
docker logs data_service | findstr "Subscribed"

# Check tick count
docker exec timescaledb psql -U trader -d trading -c "SELECT COUNT(*) FROM tick_data;"
```

### Historical Data Returns Empty

**Symptom**: Historical loader runs but fetches no data

**Cause**: Attempting to fetch data for non-trading day (Saturday, Sunday, holiday)

**Solution**: Only fetch data for trading days (Monday-Friday, excluding holidays)

**Verification**:
```bash
# Check what day you're fetching
# Saturday/Sunday will return empty
docker exec data_service python /app/services/data_service/load/historical_batch_loader.py --date 2025-10-17
```

### Database Connection Failed

**Symptom**: `Connection refused` errors

**Check**:
```bash
# Is TimescaleDB running?
docker ps | findstr timescaledb

# Can you connect manually?
docker exec -it timescaledb psql -U trader -d trading

# Check service logs
docker logs timescaledb
```

**Fix**:
```bash
# Restart database
docker-compose restart timescaledb

# Verify health
docker exec timescaledb pg_isready -U trader
```

---

## 🔧 Diagnostic Commands

### Check All Services
```bash
# List running containers
docker-compose ps

# Check specific service
docker logs data_service --tail 50

# Monitor real-time
docker logs -f data_service
```

### Database Diagnostics
```bash
# Connect to database
docker exec -it timescaledb psql -U trader -d trading

# Check table sizes
SELECT 
    schemaname, 
    tablename, 
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public';

# Check recent data
SELECT COUNT(*), MAX(timestamp) as last_tick FROM tick_data;
```

### Network Diagnostics
```bash
# Test connectivity between services
docker exec data_service ping timescaledb
docker exec data_service ping kafka
docker exec data_service ping minio

# Check DNS resolution
docker exec data_service nslookup timescaledb
```

### Storage Diagnostics
```bash
# Check MinIO buckets
docker exec minio mc ls minio/

# List historical data
docker exec minio mc ls minio/market-data/historical/

# Check disk space
docker exec minio df -h
```

---

## 📊 Health Check Endpoints

```bash
# Data Service Health
curl http://localhost:8080/api/v1/health

# Auth Service Health  
curl http://localhost:8018/health

# All services
for port in 8018 8080 8020 8030 8040 8070; do
    echo "Checking port $port..."
    curl http://localhost:$port/health 2>/dev/null || echo "Not responding"
done
```

---

## 🔄 Recovery Procedures

### Restart Single Service
```bash
docker-compose restart data_service
docker logs -f data_service
```

### Restart All Services
```bash
docker-compose restart
docker-compose ps
```

### Full System Reset
```bash
# WARNING: This will delete all data!
docker-compose down -v
docker-compose up --build -d
```

### Database Recovery
```bash
# Backup first!
docker exec timescaledb pg_dump -U trader trading > backup.sql

# Restore from backup
docker exec -i timescaledb psql -U trader -d trading < backup.sql
```

---

## 📞 Escalation Path

If issues persist after troubleshooting:

1. **Gather diagnostic info**:
   ```bash
   # Save all logs
   docker-compose logs > all_logs.txt
   
   # Save service status
   docker-compose ps > service_status.txt
   
   # Save database stats
   docker exec timescaledb psql -U trader -d trading -c "\d+" > db_schema.txt
   ```

2. **Check documentation**:
   - [Architecture docs](../../architecture/)
   - [Service docs](../../services/)
   - [Guides](../../guides/)

3. **Review recent changes**:
   - Check git log
   - Review deployment history
   - Check configuration changes

---

## 📚 Related Documentation

- [Testing](../testing/) - Test procedures
- [Data Service](../../services/data_service/) - Service documentation
- [Architecture](../../architecture/) - System design
- [Reports](../../reports/) - Status reports
