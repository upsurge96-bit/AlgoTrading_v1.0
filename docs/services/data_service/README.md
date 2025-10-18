# Data Service

Market data streaming and storage service for the AlgoTrading platform.

## Features

### 1. Live Data Streaming
- **WebSocket Integration**: Connects to Zerodha Kite WebSocket API
- **Real-time Ticks**: Streams live market data during trading hours
- **Multiple Modes**: Supports `ltp`, `quote`, and `full` modes
- **Auto-reconnection**: Automatically reconnects on connection failures
- **Token Management**: Fetches access tokens from auth service

### 2. Data Storage

#### TimescaleDB (1 Year Historical Data)
- Real-time tick data storage
- OHLCV candle data (1m, 5m, 15m, 1h, 1d)
- Automatic compression and retention policies
- Continuous aggregates for performance
- Optimized for time-series queries

#### MinIO (5 Years Historical Data)
- Long-term archival storage
- Parquet format for efficiency
- Organized by date, instrument, and interval
- Incremental daily updates
- Cost-effective cold storage

### 3. Data Processing
- **Tick Processor**: Handles tick data ingestion
  - Store to TimescaleDB
  - Publish to Kafka
  - Batch to MinIO
- **OHLCV Processor**: Handles candle data
  - Aggregation from ticks
  - Historical data loading
  - Multi-timeframe support

### 4. Kafka Integration
- Publishes all tick data to Kafka topics
- Enables other services to consume market data
- Real-time event streaming
- Partitioned by instrument token

### 5. API Endpoints

#### Data Query Endpoints
- `GET /api/ticks/latest` - Get latest ticks for instruments
- `GET /api/ticks/history` - Get historical tick data
- `GET /api/ohlcv` - Get OHLCV candle data
- `GET /api/instruments` - Search instruments
- `GET /api/instruments/{token}` - Get instrument details
- `GET /api/stats` - Get service statistics

#### Control Endpoints
- `POST /api/websocket/subscribe` - Subscribe to instruments
- `POST /api/websocket/unsubscribe` - Unsubscribe from instruments
- `POST /api/historical/fetch` - Trigger historical data fetch

#### Health & Monitoring
- `GET /health` - Health check
- `GET /metrics` - Prometheus metrics

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Data Service                            │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────────┐      ┌──────────────────┐            │
│  │  Kite WebSocket  │      │  Kite REST API   │            │
│  │     Client       │      │  (Historical)    │            │
│  └────────┬─────────┘      └────────┬─────────┘            │
│           │                          │                       │
│           v                          v                       │
│  ┌──────────────────┐      ┌──────────────────┐            │
│  │  Tick Processor  │      │ OHLCV Processor  │            │
│  └────────┬─────────┘      └────────┬─────────┘            │
│           │                          │                       │
│     ┌─────┴──────┬───────────────────┴─────┐               │
│     │            │                           │               │
│     v            v                           v               │
│ ┌────────┐  ┌────────┐               ┌──────────┐          │
│ │TimescaleDB Kafka   │               │  MinIO   │          │
│ │  (1 year) │ Topics │               │(5 years) │          │
│ └──────────┘ └────────┘               └──────────┘          │
│                                                               │
│  ┌──────────────────────────────────────────────┐           │
│  │         FastAPI Endpoints                     │           │
│  │  - Data Queries                               │           │
│  │  - WebSocket Control                          │           │
│  │  - Historical Fetch                           │           │
│  └──────────────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────────┘
```

## Database Schema

### TimescaleDB Tables

#### `tick_data` (Hypertable)
- Live tick data from WebSocket
- Partitioned by time (1 day chunks)
- Retention: 1 year
- Compression after 7 days

#### `ohlcv_data` (Hypertable)
- OHLCV candle data
- Multiple timeframes (1m, 5m, 15m, 1h, 1d)
- Partitioned by time (7 day chunks)
- Retention: 5 years
- Compression after 30 days

#### `instrument_master`
- Instrument metadata
- Trading symbols, exchanges, contract details

#### `data_service_metadata`
- Service metadata and status tracking

### Continuous Aggregates
- `ohlcv_1min` - 1-minute candles from ticks
- `ohlcv_5min` - 5-minute candles from 1-min
- `ohlcv_daily` - Daily candles from 1-min

## Configuration

### Environment Variables

```bash
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
ADMIN_API_KEY=your_admin_api_key

# Kite API
KITE_API_KEY=your_kite_api_key

# Workers
ENABLE_WORKERS=true
ENABLE_LIVE_STREAMING=true
ENABLE_HISTORICAL_FETCH=false
ENABLE_SCHEDULER=false

# WebSocket
WEBSOCKET_MODE=full  # ltp, quote, or full
INSTRUMENT_TOKENS=408065,884737  # Comma-separated

# Service
DATA_SERVICE_PORT=8080
LOG_LEVEL=info
```

## Usage

### Starting the Service

```bash
# Start with Docker Compose
docker-compose up data_service

# Start standalone
python -m services.data_service.main
```

### Running Workers Separately

```bash
# Run data workers
python -m services.data_service.workers
```

### API Examples

```bash
# Get latest tick for INFY (408065)
curl http://localhost:8080/api/ticks/latest?instrument_tokens=408065

# Get 1-day OHLCV candles
curl "http://localhost:8080/api/ohlcv?instrument_token=408065&interval=1d&limit=100"

# Get service stats
curl http://localhost:8080/api/stats

# Subscribe to instruments
curl -X POST http://localhost:8080/api/websocket/subscribe \
  -H "Content-Type: application/json" \
  -d '{"instrument_tokens": [408065, 884737], "mode": "full"}'
```

## Development

### Running Migrations

```bash
# Run manually
python -m services.data_service.db.migrate
```

### Testing

```bash
# Test WebSocket connection
python -m services.data_service.extraction.live_data

# Test historical data fetch
python -m services.data_service.extraction.historical_data

# Test processors
python -m services.data_service.processors.tick_processor
```

## Monitoring

### Prometheus Metrics
- Available at `/metrics`
- Includes tick processing rates, error counts, etc.

### Logs
- Structured JSON logging
- Log level configurable via LOG_LEVEL
- Logs available in `/logs` directory

### Health Checks
- `/health` - Service health
- Database connectivity checked automatically
- Auth service connectivity monitored

## Scheduled Tasks

### Daily (4:00 PM IST)
- Incremental historical data fetch
- Previous day's data loaded

### Weekly (Sunday 2:00 AM IST)
- Full week backfill
- Data consistency check

## Performance

### Tick Processing
- Handles 1000+ ticks/second
- Batch processing to MinIO every 60 seconds or 1000 ticks
- Asynchronous database writes

### Data Retention
- TimescaleDB: 1 year (configurable)
- MinIO: 5 years (configurable)
- Automatic compression and cleanup

## Troubleshooting

### No ticks received
1. Check auth service is running and token is valid
2. Verify INSTRUMENT_TOKENS are correct
3. Check market hours (9:15 AM - 3:30 PM IST)
4. Review logs for WebSocket errors

### Database connection errors
1. Ensure TimescaleDB is running
2. Check DATABASE_URL configuration
3. Run migrations manually

### MinIO upload failures
1. Verify MinIO is accessible
2. Check credentials in environment
3. Ensure bucket exists

## License

Proprietary - Internal use only
