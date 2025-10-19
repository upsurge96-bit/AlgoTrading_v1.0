# Live Data Processor - Real-Time Market Data Streaming

**Real-time WebSocket connection to Kite API for live market data processing**

## Overview

The Live Data Processor connects to Zerodha Kite WebSocket API and:
- 📡 Receives real-time tick data (every 3 seconds during market hours)
- 💾 Stores raw ticks to TimescaleDB for analysis
- 🕯️ Aggregates ticks into multi-granularity candles (1m, 5m, 15m, 1h, 1d)
- 📊 Stores candles to TimescaleDB for strategy consumption
- 🔄 Auto-reconnects on connection loss
- 📝 Comprehensive logging and statistics

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│               Kite WebSocket API (wss://ws.kite.trade)      │
│   Streams: LTP / Quote / Full (with market depth)          │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼ Real-time ticks (3sec intervals)
┌─────────────────────────────────────────────────────────────┐
│              LiveDataProcessor (Async)                      │
│  - on_tick() callback                                       │
│  - Auto-reconnection logic                                  │
│  - Statistics tracking                                      │
└─────────────────────────────────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
  ┌──────────┐      ┌──────────┐     ┌──────────┐
  │ Tick     │      │ Multi-   │     │  Kafka   │
  │Processor │      │Granularity│     │ Publisher│
  │          │      │Aggregator │     │          │
  └──────────┘      └──────────┘     └──────────┘
        │                 │                 │
        ▼                 ▼                 ▼
  ┌──────────┐      ┌──────────┐     ┌──────────┐
  │TimescaleDB│      │TimescaleDB│     │  Kafka   │
  │tick_data │      │ohlcv_data │     │  Topics  │
  └──────────┘      └──────────┘     └──────────┘
```

## Configuration

### Environment Variables

```bash
# Symbols to stream (comma-separated instrument tokens)
LIVE_DATA_SYMBOLS=408065,884737,738561

# WebSocket mode (ltp, quote, full)
LIVE_DATA_MODE=full

# Candle intervals to generate
LIVE_DATA_INTERVALS=1m,5m,15m,1h,1d

# Feature toggles
ENABLE_TICK_STORAGE=true
ENABLE_CANDLE_GENERATION=true

# Auth Service
AUTH_SERVICE_URL=http://auth_service:8018
ADMIN_API_KEY=your_admin_key

# Kite API
KITE_API_KEY=your_api_key

# Database
DATABASE_URL=postgresql://trader:traderpass@timescaledb:5432/trading

# Kafka (optional)
ENABLE_KAFKA=true
KAFKA_BROKERS=kafka:9092
```

### Default Configuration

If environment variables not set:
- **Symbols**: Loaded from `config.yaml` or defaults to [408065, 884737, 738561]
- **Mode**: `full` (complete tick data with market depth)
- **Intervals**: `1m,5m,15m,1h,1d`
- **Tick Storage**: Enabled
- **Candle Generation**: Enabled

## WebSocket Modes

| Mode | Data Included | Packet Size | Use Case |
|------|---------------|-------------|----------|
| **ltp** | Last price only | 8 bytes | Price monitoring, alerts |
| **quote** | OHLC, volume, buy/sell qty | 44 bytes | Basic trading, charts |
| **full** | All quote data + market depth | 184 bytes | Order book analysis, depth charts |

**Recommendation**: Use `full` mode for maximum flexibility unless bandwidth is constrained.

## Usage

### 1. Basic Usage (Default Config)

```bash
# Inside data_service container
python /app/services/data_service/load/live_data.py
```

**What it does**:
- Loads symbols from config
- Uses `full` mode
- Generates all intervals (1m, 5m, 15m, 1h, 1d)
- Stores ticks and candles to TimescaleDB

### 2. Custom Symbols and Mode

```bash
# Stream specific symbols in quote mode
python /app/services/data_service/load/live_data.py \
  --symbols 408065,884737 \
  --mode quote \
  --intervals 1m,5m
```

### 3. Tick Storage Only (No Candles)

```bash
# Store raw ticks, skip candle generation
python /app/services/data_service/load/live_data.py --no-candles
```

### 4. Candle Generation Only (No Ticks)

```bash
# Generate candles, skip raw tick storage
python /app/services/data_service/load/live_data.py --no-tick-storage
```

### 5. Minimal Mode (LTP Only)

```bash
# Lightweight streaming, last price only
python /app/services/data_service/load/live_data.py \
  --mode ltp \
  --no-candles
```

## Docker Integration

### Run as Standalone Container

```yaml
# Add to docker-compose.yml
live_data_processor:
  <<: *base-service
  build:
    context: .
    dockerfile: ./services/data_service/Dockerfile
  container_name: live_data_processor
  command: python /app/services/data_service/load/live_data.py
  environment:
    - LIVE_DATA_SYMBOLS=408065,884737,738561
    - LIVE_DATA_MODE=full
    - LIVE_DATA_INTERVALS=1m,5m,15m,1h,1d
  env_file:
    - .env
    - ./config/secrets.env
  depends_on:
    - auth_service
    - timescaledb
    - kafka
  networks:
    - monitoring-net
  restart: always
```

**Start**:
```bash
docker-compose up -d live_data_processor
```

### Run Inside Existing Container

```bash
# Start in background
docker exec -d data_service python /app/services/data_service/load/live_data.py

# View logs
docker logs -f data_service
```

## Data Flow

### Tick Processing Pipeline

```
1. WebSocket Tick Received
   ↓
2. on_tick() Callback
   ↓
3. Timezone Normalization (IST → UTC)
   ↓
4. Branch Processing:
   │
   ├─→ TickProcessor.process_tick()
   │   ├─ Store to TimescaleDB (tick_data table)
   │   ├─ Publish to Kafka (market_data topic)
   │   └─ Batch to MinIO (every 1000 ticks or 60 seconds)
   │
   └─→ MultiGranularityProcessor.process_tick()
       ├─ Aggregate into 1m candles
       ├─ Aggregate into 5m candles (direct)
       └─ Hierarchical aggregation:
           ├─ 1m → 15m
           ├─ 1m → 1h
           └─ 1m → 1d
       ↓
   Store Candles to:
   ├─ TimescaleDB (ohlcv_data table)
   ├─ Kafka (candles_1m, candles_5m, etc.)
   └─ MinIO (partitioned Parquet)
```

### Example Tick Data

**LTP Mode**:
```json
{
  "instrument_token": 408065,
  "last_price": 18500.50,
  "mode": "ltp",
  "timestamp": "2025-10-19T14:30:15+05:30"
}
```

**Quote Mode**:
```json
{
  "instrument_token": 408065,
  "last_price": 18500.50,
  "last_quantity": 75,
  "average_price": 18495.25,
  "volume": 1250000,
  "buy_quantity": 625000,
  "sell_quantity": 625000,
  "open": 18450.00,
  "high": 18520.75,
  "low": 18430.25,
  "close": 18500.50,
  "mode": "quote",
  "timestamp": "2025-10-19T14:30:15+05:30"
}
```

**Full Mode** (includes all quote fields + depth):
```json
{
  "instrument_token": 408065,
  "last_price": 18500.50,
  "...": "...all quote fields...",
  "depth": {
    "buy": [
      {"quantity": 150, "price": 18500.00, "orders": 12},
      {"quantity": 225, "price": 18499.50, "orders": 18},
      ...5 levels...
    ],
    "sell": [
      {"quantity": 175, "price": 18500.50, "orders": 15},
      {"quantity": 200, "price": 18501.00, "orders": 20},
      ...5 levels...
    ]
  },
  "mode": "full",
  "timestamp": "2025-10-19T14:30:15+05:30"
}
```

## Logging

### Log Levels

- **INFO**: Connection status, tick counts, candle generation
- **WARNING**: Disconnections, reconnection attempts
- **ERROR**: Processing errors, database failures, WebSocket errors
- **DEBUG**: Individual tick data, detailed processing steps

### Sample Logs

```
2025-10-19 14:30:00 | INFO | live_data_processor | 🚀 Starting Live Data Processor...
2025-10-19 14:30:01 | INFO | live_data_processor | ✅ LiveDataProcessor initialized
2025-10-19 14:30:01 | INFO | live_data_processor |    Symbols: 3 instruments
2025-10-19 14:30:01 | INFO | live_data_processor |    Mode: full
2025-10-19 14:30:01 | INFO | live_data_processor |    Intervals: 1m, 5m, 15m, 1h, 1d
2025-10-19 14:30:02 | INFO | live_data_processor | ================================================================================
2025-10-19 14:30:02 | INFO | live_data_processor | 🟢 WebSocket CONNECTED - Live data streaming started
2025-10-19 14:30:02 | INFO | live_data_processor | ================================================================================
2025-10-19 14:30:03 | INFO | live_data_processor | 📡 Subscribing to 3 instruments...
2025-10-19 14:30:03 | INFO | live_data_processor | ⚙️  Setting mode to 'full'...
2025-10-19 14:30:04 | INFO | live_data_processor | ✅ Live data streaming active
2025-10-19 14:30:15 | INFO | live_data_processor | 📊 Processed 100 ticks | Stored: 100 | Candles: 0 | Errors: 0
2025-10-19 14:31:00 | INFO | live_data_processor | 🕯️  Candle generated: 1m | Token: 408065 | Time: 2025-10-19 14:30:00 | OHLC: 18450.00/18520.75/18430.25/18500.50 | Vol: 1250000
```

### Statistics Logging

Every 5 minutes, detailed statistics are logged:

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
   Candle Stats:
      candles_1m: 45
      candles_5m: 15
      candles_15m: 5
      candles_1h: 0
      candles_1d: 0
================================================================================
```

## Error Handling

### Auto-Reconnection

The processor automatically handles:
- **Connection drops**: Auto-reconnects with exponential backoff
- **Token expiry**: Refreshes access token before reconnecting
- **Network errors**: Retries up to 10 times with increasing delays

**Reconnection Logic**:
```
Attempt 1: Wait 5s
Attempt 2: Wait 10s
Attempt 3: Wait 20s
Attempt 4: Wait 40s
...up to 60s max
```

### Error Types

| Error | Behavior | Action |
|-------|----------|--------|
| WebSocket disconnect | Auto-reconnect | Refresh token, reconnect |
| Tick processing error | Log and continue | Increment error counter |
| Database error | Log and skip tick | Continue with next tick |
| Candle generation error | Log and continue | Skip candle, continue streaming |

### Graceful Shutdown

On `SIGINT` (Ctrl+C) or `SIGTERM`:
1. Stop receiving new ticks
2. Close WebSocket connection
3. Flush pending candles
4. Close database connections
5. Log final statistics
6. Exit cleanly

## Performance

### Throughput

- **Ticks per second**: ~100-500 (depends on market activity)
- **Candles per minute**: 15-75 (depends on intervals enabled)
- **Database writes**: Batched for efficiency
- **MinIO writes**: Batched (1000 ticks or 60 seconds)

### Resource Usage

- **Memory**: 200-500 MB
- **CPU**: 5-15% (single core)
- **Network**: 100-500 KB/s (full mode)
- **Database connections**: Pool of 10 (configurable)

### Optimization Tips

1. **Use `quote` mode instead of `full`** if market depth not needed (75% bandwidth reduction)
2. **Disable tick storage** if only candles needed (50% database load reduction)
3. **Reduce intervals** - Only generate needed granularities
4. **Increase batch size** - Trade latency for throughput

## Monitoring

### Check if Running

```bash
# Check process
docker exec live_data_processor ps aux | grep live_data

# Check logs
docker logs -f live_data_processor

# Check connection status
docker logs live_data_processor | grep "WebSocket CONNECTED"
```

### Verify Data in Database

```bash
# Check recent ticks
docker exec timescaledb psql -U trader -d trading -c "
SELECT instrument_token, last_price, timestamp 
FROM tick_data 
ORDER BY timestamp DESC 
LIMIT 10;"

# Check generated candles
docker exec timescaledb psql -U trader -d trading -c "
SELECT interval, COUNT(*), MAX(timestamp) as latest
FROM ohlcv_data
WHERE timestamp > NOW() - INTERVAL '1 hour'
GROUP BY interval;"
```

### Query Statistics

From Python:
```python
from services.data_service.load.live_data import LiveDataProcessor

# Assuming processor is running...
stats = processor.get_stats()
print(stats)
```

## Integration with Trading Strategies

### Subscribe to Candle Updates

Strategies can consume real-time candles via Kafka:

```python
from kafka import KafkaConsumer

consumer = KafkaConsumer(
    'candles_5m',
    bootstrap_servers='kafka:9092',
    value_deserializer=lambda m: json.loads(m.decode('utf-8'))
)

for message in consumer:
    candle = message.value['data']
    
    # Process 5-minute candle
    strategy.on_candle(
        symbol=candle['instrument_token'],
        interval='5m',
        ohlcv=candle
    )
```

### Query Historical + Live Data

```python
# Query combined dataset (historical + live)
from sqlalchemy import select
from services.data_service.db.models import OHLCVData

# Get last 100 candles (includes live data)
query = select(OHLCVData).where(
    OHLCVData.instrument_token == 408065,
    OHLCVData.interval == '5m'
).order_by(OHLCVData.timestamp.desc()).limit(100)

candles = session.execute(query).scalars().all()
```

## Troubleshooting

### Issue: WebSocket won't connect

**Symptoms**: "Failed to connect after X attempts"

**Causes**:
1. Invalid API key or access token
2. Auth service down
3. Network issues

**Solutions**:
```bash
# Check auth service
curl -H "X-Admin-API-Key: your_key" http://localhost:8018/admin/token

# Verify Kite API credentials
echo $KITE_API_KEY

# Check network
ping ws.kite.trade
```

### Issue: No ticks received

**Symptoms**: "Connected: 🟢 YES" but "Ticks Received: 0"

**Causes**:
1. Non-trading hours (market closed)
2. Invalid instrument tokens
3. Not subscribed

**Solutions**:
```bash
# Check if market is open (9:15 AM - 3:30 PM IST on weekdays)
date

# Verify symbols
echo $LIVE_DATA_SYMBOLS

# Check logs for subscription confirmation
docker logs live_data_processor | grep "Subscribed"
```

### Issue: High error rate

**Symptoms**: "Errors: 500+" in statistics

**Causes**:
1. Database connection issues
2. Invalid tick data format
3. Candle generation failures

**Solutions**:
```bash
# Check database
docker exec timescaledb pg_isready -U trader

# Check logs for error details
docker logs live_data_processor | grep ERROR

# Restart processor
docker-compose restart live_data_processor
```

### Issue: Memory growing

**Symptoms**: Container memory usage increasing over time

**Causes**:
1. Tick batch not flushing
2. Candle buffer not clearing
3. Memory leak

**Solutions**:
```bash
# Check batch sizes in stats
docker logs live_data_processor | grep "Tick Batch Size"

# Restart processor (flushes buffers)
docker-compose restart live_data_processor

# Monitor memory
docker stats live_data_processor
```

## Best Practices

1. **Run in dedicated container**: Isolate from other services for stability
2. **Monitor logs daily**: Check for errors, connection issues
3. **Verify data quality**: Spot-check ticks and candles in database
4. **Use appropriate mode**: `quote` for most cases, `full` only if depth needed
5. **Enable only needed features**: Disable tick storage if only candles needed
6. **Set resource limits**: Configure Docker memory/CPU limits
7. **Configure alerts**: Set up monitoring for disconnections, errors

## Comparison: Live vs Historical

| Aspect | Live Data | Historical Data |
|--------|-----------|-----------------|
| **Source** | WebSocket ticks | Kite API candles |
| **Frequency** | Every 3 seconds | Daily at 4:30 PM |
| **Storage** | TimescaleDB + MinIO | MinIO only |
| **Use Case** | Live trading, real-time analysis | Backtesting, historical analysis |
| **Data Format** | Ticks + aggregated candles | Pre-aggregated candles |
| **Availability** | Market hours only | Anytime (API rate limited) |

**Recommendation**: Run both for complete coverage - live data during market hours, historical loader daily for backfill.

---

**Created**: October 19, 2025  
**Status**: ✅ Production Ready  
**Maintainer**: AlgoTrading Platform Team
