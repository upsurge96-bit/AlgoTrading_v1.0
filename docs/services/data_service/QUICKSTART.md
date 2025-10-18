# Data Service Quick Start Guide

## Prerequisites
1. Auth service is running and configured
2. TimescaleDB is running
3. Kafka is running
4. MinIO is running
5. You have valid Kite API credentials

## Step 1: Configure Environment Variables

Add to your `.env` file or `config/secrets.env`:

```bash
# Kite API
KITE_API_KEY=your_kite_api_key_here

# Admin API Key (for accessing auth service)
ADMIN_API_KEY=your_admin_api_key_here

# Instrument tokens to subscribe (comma-separated)
# Popular instruments:
# 408065 - INFY
# 884737 - TATA MOTORS
# 738561 - RELIANCE
# 779521 - SBIN
# 340481 - HDFCBANK
INSTRUMENT_TOKENS=408065,884737,738561

# Data Service Configuration
ENABLE_WORKERS=true
ENABLE_LIVE_STREAMING=true
ENABLE_HISTORICAL_FETCH=false
ENABLE_SCHEDULER=false
WEBSOCKET_MODE=full

# Database
DATABASE_URL=postgresql://trader:traderpass@timescaledb:5432/trading
MIGRATE_ON_STARTUP=true

# Kafka
KAFKA_BROKERS=kafka:9092
KAFKA_TOPIC=market_data

# MinIO
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioaccess
MINIO_SECRET_KEY=miniopass
MINIO_BUCKET=market-data

# Auth Service
AUTH_SERVICE_URL=http://auth_service:8018
```

## Step 2: Build the Service

```bash
cd D:\PROJECTS\AlgoTrading_v1

# Build data service
docker-compose build data_service
```

## Step 3: Run Database Migrations

```bash
# Make sure TimescaleDB is running
docker-compose up -d timescaledb

# Wait for it to be healthy
docker-compose ps timescaledb

# Run migrations
docker-compose run --rm data_service python -m services.data_service.db.migrate
```

## Step 4: Start the Service

```bash
# Start data service with all dependencies
docker-compose up data_service

# Or run in background
docker-compose up -d data_service

# View logs
docker-compose logs -f data_service
```

## Step 5: Verify Service is Running

### Check Health
```bash
curl http://localhost:8080/health
```

Expected response:
```json
{
  "status": "ok",
  "service": "data_service",
  "version": "1.0.0"
}
```

### Check Stats
```bash
curl http://localhost:8080/api/stats
```

### Check Latest Ticks
```bash
curl "http://localhost:8080/api/ticks/latest?instrument_tokens=408065"
```

## Step 6: Load Historical Data (Optional)

### Option 1: Via API
```bash
curl -X POST http://localhost:8080/api/historical/fetch \
  -H "Content-Type: application/json" \
  -d '{
    "instrument_tokens": [408065, 884737],
    "years": 5
  }'
```

### Option 2: Via Environment Variable
Set in your `.env`:
```bash
ENABLE_HISTORICAL_FETCH=true
```

Then restart the service:
```bash
docker-compose restart data_service
```

## Step 7: Monitor the Service

### View Logs
```bash
# Real-time logs
docker-compose logs -f data_service

# Last 100 lines
docker-compose logs --tail=100 data_service
```

### Check Prometheus Metrics
```bash
curl http://localhost:8080/metrics
```

### View Database Data
```bash
# Connect to TimescaleDB
docker-compose exec timescaledb psql -U trader -d trading

# Check tick data
SELECT COUNT(*) FROM tick_data;

# Check OHLCV data
SELECT COUNT(*) FROM ohlcv_data;

# View latest ticks
SELECT * FROM tick_data ORDER BY timestamp DESC LIMIT 10;
```

### Check MinIO Storage
1. Open browser: http://localhost:9001
2. Login with credentials (minioaccess/miniopass)
3. Browse `market-data` bucket
4. Check `ticks/` and `ohlcv/` folders

### Check Kafka Topics
```bash
# List topics
docker-compose exec kafka kafka-topics --bootstrap-server localhost:9092 --list

# Consume messages
docker-compose exec kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic market_data \
  --from-beginning
```

## Common Use Cases

### Subscribe to More Instruments
```bash
curl -X POST http://localhost:8080/api/websocket/subscribe \
  -H "Content-Type: application/json" \
  -d '{
    "instrument_tokens": [779521, 340481],
    "mode": "full"
  }'
```

### Get OHLCV Data
```bash
# Daily candles for last 30 days
curl "http://localhost:8080/api/ohlcv?instrument_token=408065&interval=1d&limit=30"

# 1-minute candles for last hour
curl "http://localhost:8080/api/ohlcv?instrument_token=408065&interval=1m&limit=60"
```

### Search Instruments
```bash
# Search by symbol
curl "http://localhost:8080/api/instruments?search=INFY"

# Filter by exchange
curl "http://localhost:8080/api/instruments?exchange=NSE&limit=50"
```

## Troubleshooting

### No Ticks Received
1. **Check auth service**:
   ```bash
   curl http://localhost:8018/health
   curl http://localhost:8018/status
   ```

2. **Check token validity**:
   - Ensure auth service has a valid token
   - Check token expiry time

3. **Check market hours**:
   - Indian markets: 9:15 AM - 3:30 PM IST (Mon-Fri)
   - No data during weekends/holidays

4. **Check logs**:
   ```bash
   docker-compose logs data_service | grep -i "websocket\|error"
   ```

### Database Connection Errors
1. **Check TimescaleDB is running**:
   ```bash
   docker-compose ps timescaledb
   ```

2. **Run migrations**:
   ```bash
   docker-compose run --rm data_service python -m services.data_service.db.migrate
   ```

3. **Check DATABASE_URL**:
   - Ensure correct credentials
   - Ensure correct host (timescaledb not localhost)

### MinIO Upload Failures
1. **Check MinIO is running**:
   ```bash
   docker-compose ps minio
   ```

2. **Verify credentials**:
   - Check MINIO_ACCESS_KEY and MINIO_SECRET_KEY

3. **Check bucket exists**:
   - Login to MinIO console (http://localhost:9001)
   - Create `market-data` bucket if missing

### Workers Not Starting
1. **Check ENABLE_WORKERS is set**:
   ```bash
   docker-compose exec data_service env | grep ENABLE_WORKERS
   ```

2. **Check logs for errors**:
   ```bash
   docker-compose logs data_service | grep -i "worker\|error"
   ```

## Performance Tuning

### For High-Frequency Data
```bash
# Increase batch size
MINIO_BATCH_SIZE=5000
MINIO_BATCH_INTERVAL=30

# More database connections
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=30
```

### For Low Memory Systems
```bash
# Reduce batch sizes
MINIO_BATCH_SIZE=500
DATABASE_POOL_SIZE=5

# Disable some workers
ENABLE_SCHEDULER=false
```

## Next Steps

1. **Set up alerts** - Configure Prometheus alerts for service health
2. **Enable scheduler** - For automatic daily data updates
3. **Add more instruments** - Subscribe to your trading universe
4. **Integrate with strategy service** - Consume Kafka topics in strategy service
5. **Set up backups** - Configure regular backups of TimescaleDB and MinIO

## Support

- Check logs: `docker-compose logs data_service`
- Review README: `services/data_service/README.md`
- Implementation details: `services/data_service/IMPLEMENTATION_SUMMARY.md`

Happy Trading! 📈
