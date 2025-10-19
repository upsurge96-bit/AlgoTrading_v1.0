# Historical Data Loader

**Daily scheduled job to fetch and store historical market data from Kite API to MinIO**

## Overview

This module provides automated daily loading of historical market data with the following features:

- 📅 **Scheduled Execution**: Runs daily at 4:30 PM IST (configurable)
- 🎯 **Incremental Loading**: Only fetches new data, skips existing
- 📦 **Partitioned Storage**: MinIO paths organized by Symbol/Year/Month/Week/Day/Hour
- ⚙️ **Configurable**: Symbols and intervals via environment variables
- 📝 **Comprehensive Logging**: All operations logged with timestamps
- 🔄 **Error Resilient**: Continues on errors, logs failures

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                 Historical Data Loader                      │
└─────────────────────────────────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
  ┌──────────┐      ┌──────────┐     ┌──────────┐
  │Auth Svc  │      │Kite API  │     │  MinIO   │
  │(Token)   │      │(Data)    │     │(Storage) │
  └──────────┘      └──────────┘     └──────────┘
        │                 │                 │
        └────────┬────────┘                 │
                 ▼                          ▼
         Fetch Historical Data    Store in Partitioned
         for Previous Day         Parquet Format
```

## Storage Structure

Data is stored in MinIO with hierarchical partitioning:

```
market-data/
└── historical/
    └── {symbol_name}/          # e.g., NIFTY50
        └── {year}/             # e.g., 2025
            └── {month}/        # e.g., 10
                └── {week}/     # e.g., 42
                    └── {day}/  # e.g., 18
                        └── {hour}/     # e.g., 14
                            └── {interval}.parquet  # e.g., 1m.parquet
```

**Example path**: `historical/NIFTY50/2025/10/42/18/14/1m.parquet`

## Configuration

### Environment Variables

```bash
# Symbols to load (comma-separated instrument tokens)
HISTORICAL_SYMBOLS=408065,884737,738561

# Intervals to fetch (Kite API format)
HISTORICAL_INTERVALS=minute,5minute,15minute,60minute,day

# Daily schedule time (HH:MM in IST)
HISTORICAL_SCHEDULE_TIME=16:30

# MinIO Configuration
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioaccess
MINIO_SECRET_KEY=miniopass
MINIO_BUCKET=market-data
MINIO_SECURE=false

# Auth Service
AUTH_SERVICE_URL=http://auth_service:8018
ADMIN_API_KEY=your_admin_key

# Kite API
KITE_API_KEY=your_api_key
```

### Default Symbols

If `HISTORICAL_SYMBOLS` is not set, loads from `config.yaml` or uses defaults:

- 408065 - NIFTY 50
- 884737 - BANKNIFTY
- 738561 - INFY

### Interval Mapping

| Kite API Interval | Normalized | Description |
|-------------------|------------|-------------|
| `minute`          | `1m`       | 1 minute    |
| `5minute`         | `5m`       | 5 minutes   |
| `15minute`        | `15m`      | 15 minutes  |
| `30minute`        | `30m`      | 30 minutes  |
| `60minute`        | `1h`       | 1 hour      |
| `day`             | `1d`       | 1 day       |

## Usage

### 1. Scheduled Mode (Production)

Run the scheduler to execute daily at configured time:

```bash
# Inside data_service container
python /app/services/data_service/load/scheduler.py

# Custom schedule time
python /app/services/data_service/load/scheduler.py --schedule-time 17:00
```

**Docker Compose Integration**:

Add to `docker-compose.yml`:

```yaml
historical_data_scheduler:
  <<: *base-service
  build:
    context: .
    dockerfile: ./services/data_service/Dockerfile
  container_name: historical_data_scheduler
  command: python /app/services/data_service/load/scheduler.py
  environment:
    - HISTORICAL_SYMBOLS=408065,884737,738561
    - HISTORICAL_INTERVALS=minute,5minute,15minute,60minute,day
    - HISTORICAL_SCHEDULE_TIME=16:30
  env_file:
    - .env
    - ./config/secrets.env
  depends_on:
    - auth_service
    - minio
  networks:
    - monitoring-net
  restart: always
```

### 2. Manual Mode (Testing)

Load data for specific date:

```bash
# Load yesterday's data
python /app/services/data_service/load/historical_data.py

# Load specific date
python /app/services/data_service/load/historical_data.py --date 2025-10-18

# Custom symbols
python /app/services/data_service/load/historical_data.py \
  --symbols 408065,884737 \
  --intervals minute,day \
  --date 2025-10-18
```

### 3. Test Scheduler Immediately

Run scheduled job right now (bypass schedule):

```bash
python /app/services/data_service/load/scheduler.py --run-now
```

## Workflow

### Daily Schedule Flow

1. **Trigger**: Scheduler wakes up at 4:30 PM IST
2. **Date Calculation**: Determines previous trading day
3. **Symbol Loop**: For each configured symbol:
   - Get symbol name from token mapping
   - For each interval:
     - Check if data exists in MinIO (skip if yes)
     - Fetch from Kite API (9:15 AM - 3:30 PM)
     - Store to MinIO in partitioned Parquet format
     - Log result (success/skip/fail)
4. **Summary**: Log completion statistics
5. **Wait**: Sleep until next scheduled time

### Data Existence Check

Before fetching, loader checks MinIO for existing data:

```python
# Path: historical/NIFTY50/2025/10/18/09/1m.parquet
if exists_in_minio(path):
    log("⏭️ Data already exists, skipping")
    continue
```

This prevents:
- Duplicate API calls
- Wasted bandwidth
- Overwriting existing data

## Logging

### Log Format

```
2025-10-19 16:30:00 | INFO | historical_data_loader | ======================================================================
2025-10-19 16:30:00 | INFO | historical_data_loader | 📅 Loading historical data for: 2025-10-18
2025-10-19 16:30:00 | INFO | historical_data_loader | ======================================================================
2025-10-19 16:30:01 | INFO | historical_data_loader | [1/15] Processing: NIFTY50 (408065) - minute
2025-10-19 16:30:02 | INFO | historical_data_loader | ✅ Fetched 375 candles for token=408065, interval=minute
2025-10-19 16:30:03 | INFO | historical_data_loader | ✅ Stored 375 records across 7 partitions to MinIO
2025-10-19 16:30:04 | INFO | historical_data_loader | [2/15] Processing: NIFTY50 (408065) - 5minute
2025-10-19 16:30:05 | INFO | historical_data_loader | ⏭️ Data already exists, skipping
```

### Log Locations

- **Container**: `/logs/historical_data_loader.log`
- **Host**: `./logs/historical_data_loader.log`

### Log Levels

- `INFO`: Normal operations, progress updates
- `WARNING`: No data returned, existing data skipped
- `ERROR`: API failures, storage errors
- `DEBUG`: Detailed fetch/store operations

## Error Handling

### Behavior on Errors

The loader is designed to be resilient:

1. **Continue on Failure**: If one symbol/interval fails, others continue
2. **Log All Errors**: Errors logged with full context
3. **Summary Report**: Final stats show failed count
4. **Retry Logic**: API client has built-in retries (3 attempts)

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| "Failed to get access token" | Auth service down | Check auth_service health |
| "API error: 403" | Invalid/expired token | Regenerate token via auth UI |
| "No data returned" | Non-trading day or invalid date | Normal - logs warning |
| "Error storing to MinIO" | MinIO connection issue | Check MinIO container |

## Performance

### Typical Execution Time

For 3 symbols × 5 intervals = 15 tasks:

- **With existing data**: 5-10 seconds (checks only)
- **Fresh load**: 2-3 minutes (fetch + store)
- **Full day (7 symbols × 5 intervals)**: 5-8 minutes

### Rate Limiting

- 0.5s delay between API calls to respect Kite rate limits
- Prevents `429 Too Many Requests` errors

### Resource Usage

- **Memory**: ~200MB (Pandas DataFrames)
- **Network**: ~10-50MB per day (depends on intervals)
- **Storage**: ~5-20MB per symbol per day (Parquet compressed)

## Monitoring

### Health Checks

Check if loader is running:

```bash
# Check scheduler process
docker exec historical_data_scheduler ps aux | grep scheduler

# Check logs
docker logs -f historical_data_scheduler
```

### Verify Data in MinIO

```bash
# List objects for specific symbol
docker exec minio mc ls minio/market-data/historical/NIFTY50/ --recursive

# Check today's data
docker exec minio mc ls minio/market-data/historical/NIFTY50/2025/10/ --recursive
```

### Query Stored Data

```python
from services.data_service.load.historical_data import HistoricalDataLoader
from datetime import datetime

loader = HistoricalDataLoader()

# Check if data exists
exists = loader.check_existing_data(
    symbol_name="NIFTY50",
    date=datetime(2025, 10, 18, 14, 0),
    interval="1m"
)
print(f"Data exists: {exists}")
```

## Troubleshooting

### Issue: Scheduler not running

```bash
# Check if container is up
docker ps | grep historical_data_scheduler

# Check logs for errors
docker logs historical_data_scheduler

# Restart scheduler
docker-compose restart historical_data_scheduler
```

### Issue: Data not loading

1. **Check auth token**:
   ```bash
   curl -H "X-Admin-API-Key: your_key" http://localhost:8018/admin/token
   ```

2. **Check MinIO connectivity**:
   ```bash
   docker exec minio mc ls minio/
   ```

3. **Run manual test**:
   ```bash
   docker exec data_service python /app/services/data_service/load/scheduler.py --run-now
   ```

### Issue: Duplicate data

Data existence check failed. Manually remove duplicates:

```bash
# List objects for date
docker exec minio mc ls minio/market-data/historical/NIFTY50/2025/10/18/ --recursive

# Remove specific partition (if needed)
docker exec minio mc rm minio/market-data/historical/NIFTY50/2025/10/18/14/1m.parquet
```

## Integration with Data Pipeline

The historical data loader complements the real-time pipeline:

```
┌────────────────────────────────────────────────────┐
│           Real-Time Data Pipeline                  │
│  (Live ticks → 1m → 5m → 15m → 1h → 1d)          │
│  Storage: TimescaleDB + MinIO + Kafka             │
└────────────────────────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────┐
│         Historical Data Loader (Daily)             │
│  Fetches previous day's data at 4:30 PM IST       │
│  Storage: MinIO (Symbol/Year/Month/Week/Day/Hour) │
└────────────────────────────────────────────────────┘
                         │
                         ▼
              ┌──────────────────┐
              │  MinIO Storage   │
              │  - Real-time     │
              │  - Historical    │
              └──────────────────┘
```

**Differences**:

| Aspect | Real-Time | Historical Loader |
|--------|-----------|-------------------|
| Source | WebSocket ticks | Kite API (candles) |
| Frequency | Every 3 seconds | Daily at 4:30 PM |
| Storage | TimescaleDB + MinIO | MinIO only |
| Partitioning | Year/Month/Week/Day/Hour/Interval | Symbol/Year/Month/Week/Day/Hour |
| Use Case | Live trading | Backtesting, analysis |

## Best Practices

1. **Set `HISTORICAL_SYMBOLS` carefully**: Only include symbols you need to minimize API calls
2. **Monitor logs daily**: Check for failures and adjust configuration
3. **Verify data periodically**: Spot-check MinIO for data completeness
4. **Use separate container**: Run scheduler in dedicated container to avoid interference
5. **Configure alerts**: Set up monitoring alerts for scheduler failures

## Future Enhancements

- [ ] Support for custom date ranges (backfill mode)
- [ ] Automatic symbol discovery from database
- [ ] Parallel fetching for multiple symbols
- [ ] Data quality validation (gap detection)
- [ ] Metrics export (Prometheus)
- [ ] Email/Slack notifications on failures
- [ ] Integration with TimescaleDB for querying

---

**Created**: October 19, 2025  
**Status**: ✅ Production Ready  
**Maintainer**: AlgoTrading Platform Team
