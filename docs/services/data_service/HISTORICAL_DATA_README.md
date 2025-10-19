# Historical Data Management System

## Overview

This system fetches 5 years of historical market data from Kite API and stores it in MinIO with detailed partitioning for efficient querying and analysis.

## Partition Structure

Data is organized hierarchically for optimal query performance:

```
MinIO Bucket: market-data/
│
├── ohlcv/                    # OHLCV (candlestick) data
│   └── YYYY/                 # Year (e.g., 2025)
│       └── MM/               # Month (01-12)
│           └── WW/           # ISO Week number (00-53)
│               └── DD/       # Day (01-31)
│                   └── HH/   # Hour (00-23)
│                       └── interval/  # e.g., 1d, 1h, 15m
│                           └── instrument_token.parquet
│
└── ticks/                    # Real-time tick data
    └── YYYY/MM/WW/DD/HH/
        └── instrument_token_HHMMSS.parquet
```

### Example Paths
- Daily candles: `ohlcv/2025/01/03/15/10/1d/408065.parquet`
- Hourly candles: `ohlcv/2025/01/03/15/10/1h/408065.parquet`
- Ticks: `ticks/2025/01/03/15/10/408065_153045.parquet`

## Features

### ✅ 5-Year Historical Backfill
- Fetches 5 years of historical data for configured instruments
- Multiple timeframes (daily, hourly, 15-minute)
- Includes Open Interest (OI) data
- Progress tracking with ETA
- Resume capability (skips existing data)

### ✅ Daily Incremental Updates
- Scheduled at 4:00 PM IST (after market close at 3:30 PM)
- Updates previous day's data
- Runs automatically via APScheduler
- Uses IST (Asia/Kolkata) timezone

### ✅ Efficient Storage
- Parquet format with Snappy compression
- Partitioned by year/month/week/day/hour
- Optimized for time-series queries
- Separate storage for different intervals

### ✅ Dual Storage
- **MinIO**: Long-term archival (5 years retention)
- **TimescaleDB**: Fast querying (1 year retention)

## Configuration

Edit `config.yaml`:

```yaml
# Instruments to fetch
instruments:
  nse_equity:
    - 408065   # INFY
    - 884737   # TATAMOTORS
    - 738561   # RELIANCE

# Historical data settings
data_fetch:
  historical:
    enabled: true
    years: 5
    intervals:
      - day
      - 60minute
      - 15minute
    include_oi: true
  
  incremental:
    enabled: true
    schedule: "0 16 * * *"  # 4 PM IST
    timezone: "Asia/Kolkata"
    days: 1
```

## Usage

### 1. Initial Backfill (5 Years)

```bash
# Full backfill of all configured instruments
cd services/data_service
python backfill_historical_data.py

# This will:
# - Fetch 5 years of data
# - Store to MinIO with detailed partitioning
# - Show progress with ETA
# - Take several hours depending on instruments
```

### 2. Single Instrument Backfill

```bash
# Backfill specific instrument
python backfill_historical_data.py --single 408065

# Useful for:
# - Testing
# - Adding new instruments
# - Re-fetching failed instruments
```

### 3. Verify Data

```bash
# Verify data was stored correctly
python backfill_historical_data.py --verify 408065 --interval day

# Checks:
# - MinIO storage
# - Partition structure
# - Data integrity
```

### 4. Custom Configuration

```bash
# Use custom config file
python backfill_historical_data.py --config /path/to/config.yaml
```

### 5. Debug Mode

```bash
# Enable debug logging
python backfill_historical_data.py --log-level DEBUG
```

## Automated Daily Updates

The system automatically updates historical data daily at 4:00 PM IST:

```python
# In workers.py - DataServiceScheduler
scheduler.add_job(
    func=run_incremental_fetch,
    trigger=CronTrigger(hour=16, minute=0, timezone="Asia/Kolkata"),
    id="daily_incremental_fetch"
)
```

### Schedule Details:
- **Time**: 4:00 PM IST (10:30 AM UTC)
- **Frequency**: Daily
- **Data Range**: Previous 1 day
- **Intervals**: day, 60minute, 15minute
- **Automatic**: Runs as long as data service is running

## Partition Benefits

### 1. Efficient Time-Range Queries
```python
# Query specific date range - only reads relevant partitions
# Example: Get January 2025 data
# Reads: ohlcv/2025/01/*
# Skips: All other months
```

### 2. Easy Data Management
```python
# Delete old data by partition
# Example: Remove 2020 data
# Delete: ohlcv/2020/*
```

### 3. Parallel Processing
```python
# Process multiple partitions in parallel
# Each hour can be processed independently
```

### 4. Incremental Backfill
```python
# Only fetch missing partitions
# Skip existing data automatically
```

## Data Flow

```
┌─────────────────┐
│   Kite API      │
│  (Historical)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│HistoricalData   │
│    Fetcher      │ ──── Chunks by 60 days
└────────┬────────┘      Rate limiting
         │
         ├──────────────┬──────────────┐
         ▼              ▼              ▼
┌─────────────┐  ┌─────────────┐  ┌──────────┐
│   MinIO     │  │TimescaleDB  │  │  Kafka   │
│  (Archive)  │  │  (Queries)  │  │ (Stream) │
└─────────────┘  └─────────────┘  └──────────┘
     │                 │
     └────────┬────────┘
              ▼
     Partition Structure:
     YYYY/MM/WW/DD/HH/
```

## Performance Considerations

### API Rate Limits
- **Kite API**: ~60 requests/minute
- **Strategy**: 0.5 second delay between requests
- **Chunking**: 60 days per request
- **Retries**: 3 attempts with exponential backoff

### Storage Estimates
Per instrument per year:
- Daily candles: ~250 records × 50 bytes = ~12 KB
- Hourly candles: ~1,500 records × 50 bytes = ~75 KB
- 15-min candles: ~6,000 records × 50 bytes = ~300 KB

For 10 instruments × 5 years × 3 intervals:
- Total: ~19.5 MB (compressed with Snappy)

### Processing Time
- Per instrument-interval: ~30 seconds
- 10 instruments × 3 intervals: ~15 minutes
- 100 instruments × 3 intervals: ~2.5 hours

## Error Handling

### Automatic Retry
```python
# Network errors: 3 retries with exponential backoff
# API rate limits: Automatic delay and retry
# Partial failures: Continue with next instrument
```

### Resume Capability
```python
# Script can be stopped and resumed
# Existing data is not re-fetched
# Progress is logged continuously
```

### Failure Tracking
```python
# All failures are logged with details
# Summary report at end of backfill
# Can re-run failed instruments separately
```

## Monitoring

### Logs
```bash
# View backfill progress
tail -f logs/data_service.log

# Check for errors
grep ERROR logs/data_service.log
```

### MinIO Console
```bash
# Access at http://localhost:9001
# Username: minioaccess
# Password: miniopass

# Browse partitions visually
# Check file sizes and counts
# Verify data organization
```

### Metrics
- Total instruments processed
- Success/failure rate
- Total data size stored
- Time taken per instrument
- API requests made

## Troubleshooting

### Issue: No data returned
```bash
# Possible causes:
# 1. Invalid instrument token
# 2. No trading on selected dates (holidays)
# 3. Expired access token

# Solution:
# - Verify instrument token
# - Check date range includes trading days
# - Refresh auth token
```

### Issue: API rate limit exceeded
```bash
# Symptoms: HTTP 429 errors

# Solution:
# - Increase delay between requests
# - Reduce max_days_per_request
# - Run during off-peak hours
```

### Issue: MinIO connection failed
```bash
# Symptoms: Connection refused

# Solution:
docker compose up -d minio
# Verify MinIO is running
docker compose ps minio
```

### Issue: Incomplete data
```bash
# Verify specific instrument
python backfill_historical_data.py --verify 408065 --interval day

# Re-fetch if needed
python backfill_historical_data.py --single 408065
```

## Best Practices

### 1. Start Small
```bash
# Test with 1-2 instruments first
# Verify data quality
# Then backfill all instruments
```

### 2. Run During Off-Peak Hours
```bash
# Best time: After market hours (4 PM - 9 AM IST)
# Avoid: Market hours (9:15 AM - 3:30 PM IST)
```

### 3. Monitor Progress
```bash
# Keep logs open
# Check MinIO periodically
# Verify disk space
```

### 4. Backup Configuration
```bash
# Save config.yaml
# Document instrument tokens
# Keep access credentials secure
```

## Next Steps

1. **Run Initial Backfill**
   ```bash
   python backfill_historical_data.py
   ```

2. **Verify Data**
   ```bash
   python backfill_historical_data.py --verify 408065 --interval day
   ```

3. **Start Data Service**
   ```bash
   docker compose up data_service
   # Daily updates will run automatically at 4 PM IST
   ```

4. **Monitor Logs**
   ```bash
   docker compose logs -f data_service
   ```

## Support

For issues or questions:
1. Check logs: `logs/data_service.log`
2. Review error messages
3. Verify configuration
4. Check MinIO console

## References

- Kite API: https://kite.trade/docs/connect/v3/historical/
- MinIO Documentation: https://min.io/docs/
- APScheduler: https://apscheduler.readthedocs.io/
- Parquet Format: https://parquet.apache.org/
