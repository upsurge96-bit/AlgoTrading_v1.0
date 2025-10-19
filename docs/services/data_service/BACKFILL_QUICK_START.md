# Historical Data Backfill - Quick Start Guide

## 🚀 Running with Docker (Recommended)

Since you're using Docker, all Python dependencies are already installed in the container. Run the backfill script using `docker compose`:

### 1. Test Single Instrument (Recommended First Step)

```bash
# Backfill single instrument (INFY - 408065) to test the system
docker compose run --rm data_service python /app/services/data_service/backfill_historical_data.py --single 408065
```

This will:
- Fetch 5 years of data for INFY
- Store to MinIO with partitioning: `ohlcv/YYYY/MM/WW/DD/HH/interval/408065.parquet`
- Take ~2-3 minutes
- Show progress and errors

### 2. Verify Data Was Stored

```bash
# Verify the data in MinIO
docker compose run --rm data_service python /app/services/data_service/backfill_historical_data.py --verify 408065 --interval day
```

### 3. Full Backfill (All Instruments)

```bash
# Backfill all instruments from config.yaml
# WARNING: This will take several hours!
docker compose run --rm data_service python /app/services/data_service/backfill_historical_data.py
```

When prompted, type `yes` to confirm.

### 4. Check MinIO Console

```bash
# Access MinIO Console at: http://localhost:9001
# Username: minioaccess
# Password: miniopass

# Browse bucket: market-data
# Look for structure: ohlcv/2025/01/03/15/10/1d/408065.parquet
```

## 📋 Command Options

```bash
# Show help
docker compose run --rm data_service python /app/services/data_service/backfill_historical_data.py --help

# Single instrument
docker compose run --rm data_service python /app/services/data_service/backfill_historical_data.py --single <TOKEN>

# Verify data
docker compose run --rm data_service python /app/services/data_service/backfill_historical_data.py --verify <TOKEN> --interval day

# Debug mode
docker compose run --rm data_service python /app/services/data_service/backfill_historical_data.py --single 408065 --log-level DEBUG
```

## 🔧 Configuration

Edit `services/data_service/config.yaml`:

```yaml
# Add/remove instruments
instruments:
  nse_equity:
    - 408065   # INFY
    - 884737   # TATAMOTORS
    - 738561   # RELIANCE

# Configure intervals
data_fetch:
  historical:
    enabled: true
    years: 5
    intervals:
      - day
      - 60minute
      - 15minute
```

## 📊 Partition Structure

Data is stored with detailed partitioning for efficient querying:

```
market-data/
└── ohlcv/
    └── 2025/              # Year
        └── 01/            # Month
            └── 03/        # Week (ISO week number)
                └── 15/    # Day
                    └── 10/  # Hour
                        └── 1d/        # Interval (day, 1h, 15m)
                            └── 408065.parquet  # Instrument token
```

## ⏰ Automatic Daily Updates

Once you start the data_service normally, it will **automatically fetch new data every day at 4:00 PM IST**:

```bash
# Start data service with scheduler
docker compose up -d data_service

# Daily updates will run automatically at 4 PM IST
# Check logs:
docker compose logs -f data_service
```

## 🐛 Troubleshooting

### Issue: Container not running
```bash
# Check container status
docker compose ps

# Rebuild if needed
docker compose build data_service
docker compose up -d data_service
```

### Issue: MinIO connection failed
```bash
# Start MinIO
docker compose up -d minio

# Check MinIO health
docker compose ps minio
```

### Issue: Auth token expired
```bash
# The script will automatically refresh tokens via auth_service
# Make sure auth_service is running:
docker compose up -d auth_service
```

### Issue: No data returned
```bash
# Possible causes:
# 1. Invalid instrument token
# 2. Weekend/holiday (no trading data)
# 3. Rate limits

# Check logs:
docker compose logs data_service

# Try different instrument:
docker compose run --rm data_service python /app/services/data_service/backfill_historical_data.py --single 738561
```

## 📈 Progress Monitoring

The script shows real-time progress:

```
================================================================================
Progress: 5/15 (33.3%)
Current: Instrument #2/5 - Token: 408065, Interval: 60minute
Elapsed: 0:02:30, ETA: 0:05:00
Success: 4, Failed: 1
================================================================================
```

## 💡 Tips

1. **Start small**: Test with 1-2 instruments first
2. **Run overnight**: Full backfill takes several hours
3. **Check MinIO**: Verify data structure is correct
4. **Monitor logs**: Watch for errors and rate limits
5. **Resume anytime**: Script can be stopped and restarted (skips existing data)

## 🎯 Next Steps

After successful backfill:

1. ✅ Verify data in MinIO Console
2. ✅ Check partition structure
3. ✅ Start data_service for daily updates
4. ✅ Monitor logs for scheduled runs at 4 PM IST

## 📚 Full Documentation

See [HISTORICAL_DATA_README.md](./HISTORICAL_DATA_README.md) for complete documentation.
