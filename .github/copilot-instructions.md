# AlgoTrading Platform - AI Agent Instructions

## Project Overview

**AlgoTrading_v1** is a microservices-based algorithmic trading platform built with FastAPI, integrating with broker APIs (Zerodha Kite), processing real-time market data, and executing trading strategies. The platform uses TimescaleDB for time-series storage, Kafka for event streaming, MinIO for historical data archiving, and includes comprehensive monitoring.

## Critical Architecture Patterns

### 1. Microservices Structure

The platform consists of 6 independent services (all FastAPI):
- **auth_service** (port 8018): Token management, broker OAuth callbacks
- **data_service** (port 8080): Market data ingestion, tick→candle aggregation
- **strategy_service** (port 8020): Trading strategies, backtesting
- **execution_service** (port 8030): Order routing and execution
- **risk_service** (port 8040): Risk monitoring, PnL tracking
- **monitoring_service** (port 8070): Health checks, metrics aggregation

**Key Pattern**: All services extend a base service pattern in `docker-compose.yml` (see `x-base-service`) with shared volumes for `core/`, `config/`, and `logs/`.

### 2. Centralized Core Utilities (CRITICAL)

**Always import from `core/utils/` - never duplicate utilities!**

```python
# ✅ CORRECT: Use centralized utilities
from core.utils.logger import get_logger, setup_logging
from core.utils.time_utils import utc_now, timestamp_ms, parse_datetime
from core.utils.config_loader import load_config

# ❌ WRONG: Creating service-specific copies
from services.my_service.logger import get_logger  # Don't do this!
```

**Why**: We eliminated duplicate `logger.py` files from `common/` and service directories. See `docs/guides/CORE_UTILITIES.md` for migration details.

### 3. Timezone Handling (MANDATORY)

**All datetime objects MUST be timezone-aware (UTC internally, IST for display)**

```python
from core.utils.time_utils import utc_now, parse_datetime, format_iso

# ✅ CORRECT: Timezone-aware datetimes
timestamp = utc_now()  # Returns datetime with UTC timezone
iso_str = format_iso(timestamp)  # ISO 8601 with timezone

# ❌ WRONG: Naive datetimes
timestamp = datetime.now()  # Missing timezone info!
```

**Logging timezone**: All logs display in IST (Asia/Kolkata) via `core/utils/logger.py`.

### 4. Dependency Injection Container

**data_service** uses a production-ready DI container pattern:

```python
# services/data_service/container.py
from services.data_service.container import get_container, DependencyProvider

# In FastAPI endpoints
from fastapi import Depends

@app.get("/endpoint")
async def endpoint(deps: DependencyProvider = Depends(get_dependencies)):
    # Access managed dependencies
    token = await deps.auth_client.get_access_token()
    await deps.tick_processor.process(tick_data)
```

**Lifecycle**: Container manages startup (`initialize()`) and shutdown (`cleanup()`) of all services (database connections, Kafka clients, MinIO handlers). See `services/data_service/main.py` lifespan context.

### 5. Multi-Granularity Data Pipeline

**Critical flow**: Ticks → 1m → 5m → 15m → 1h → 1d candles

```
WebSocket Ticks (3sec) 
  ↓
MultiGranularityProcessor (real-time)
  ↓
├─ 1m candles (direct from ticks)
├─ 5m candles (direct from ticks)  
└─ Hierarchical aggregation: 1m → 15m → 1h → 1d
  ↓
Triple storage:
  ├─ TimescaleDB (ohlcv_data table, hypertable partitioned)
  ├─ MinIO (Parquet files, partitioned by year/month/week/day/hour/interval)
  └─ Kafka (separate topics: candles_1m, candles_5m, etc.)
```

**Processors**:
- `MultiGranularityProcessor`: Real-time tick processing
- `BatchMultiGranularityProcessor`: Historical data backfills (625 candles/sec)

See `docs/MULTI_GRANULARITY_IMPLEMENTATION.md` for complete architecture.

### 6. Exception Hierarchy

**data_service** has structured exceptions with error codes (see `services/data_service/exceptions.py`):

```python
# Use specific exceptions, not generic Exception
raise AuthenticationError("Token expired", error_code=3001, details={...})
raise DatabaseError("Connection failed", error_code=2001, details={...})
```

**Error code ranges**: 1000s=Config, 2000s=Database, 3000s=Auth, 4000s=WebSocket, 5000s=Kafka, 6000s=MinIO, 7000s=Data Processing, 8000s=Worker, 9000s=API.

**Middleware**: `ErrorHandlingMiddleware` catches `DataServiceException` subclasses and returns structured JSON responses.

## Development Workflows

### Running Services

```bash
# Build and start all services
docker-compose up --build

# Start specific service
docker-compose up auth_service data_service

# View logs
docker-compose logs -f data_service

# Restart service after code changes
docker-compose restart data_service
```

**Port mapping**: Services expose ports defined in `docker-compose.yml` (auth:8018, data:8080, etc.)

### Database Operations

```bash
# Access TimescaleDB
docker exec -it timescaledb psql -U trader -d trading

# Check stored candles
SELECT interval, COUNT(*), MIN(timestamp), MAX(timestamp)
FROM ohlcv_data GROUP BY interval;

# Access pgAdmin UI
# Navigate to http://localhost:5050 (email: rahulkujur31@gmail.com, password: admin)
```

**Migration**: Set `MIGRATE_ON_STARTUP=true` in `.env` to auto-run migrations on service start.

### Testing Market Data

```bash
# Run multi-granularity demo (processes 500 ticks → all timeframes)
docker exec data_service python /app/demo_multi_granularity.py

# Backfill historical data (5 years, all instruments)
docker exec -it data_service python /app/services/data_service/backfill_historical_data.py

# Load historical data for specific date to MinIO
docker exec data_service python /app/services/data_service/load/historical_batch_loader.py --date 2025-10-18

# Run historical data loader immediately (test scheduled job)
docker exec data_service python /app/services/data_service/load/scheduler.py --run-now

# Start live data streaming
docker exec data_service python /app/services/data_service/load/realtime_stream_processor.py

# Start live data streaming (custom symbols and mode)
docker exec data_service python /app/services/data_service/load/realtime_stream_processor.py \
  --symbols 408065,884737 \
  --mode full \
  --intervals 1m,5m,15m

# Check data service health
curl http://localhost:8080/api/v1/health
```

### Heartbeat Monitoring

**Real-time data flow monitoring** - All load modules include heartbeat logging:

```bash
# Monitor heartbeat (all events)
monitor_heartbeat.bat

# Docker logs with heartbeat filter
docker logs -f data_service | findstr "HEARTBEAT"

# PowerShell (better filtering)
docker logs -f data_service 2>&1 | Select-String -Pattern "💓|ERROR|WARNING"
```

**Heartbeat Intervals**:
- **Live Data**: Every 60 seconds (configurable via `HEARTBEAT_INTERVAL`)
- **Historical Data**: Every task completion + final summary
- **Scheduler**: On start, job run, and completion

**Sample Heartbeat**:
```
💓 HEARTBEAT | Uptime: 15m | Connected: 🟢 | Ticks: 1,234 | Stored: 1,234 | Candles: 45 | Errors: 0 | Last Tick: 🟢 2s ago
```

**See**: `HEARTBEAT_MONITORING.md` for complete guide

### Auth Service - Zerodha Login Flow

1. User visits `http://localhost:8018/`
2. Frontend redirects to Zerodha OAuth page
3. User authenticates with broker
4. Zerodha calls `/callback?request_token=xxx&status=success`
5. `auth_service` exchanges request_token for access_token
6. Token stored in database (encrypted) with expiry tracking
7. Other services fetch token via `GET /admin/token` (requires `X-Admin-API-Key` header)

**Token encryption**: Uses `TOKEN_ENCRYPTION_KEY` from environment (change in production!).

## Configuration Management

### Two-Tier Config System

**Tier 1: Simple YAML** (for most services):
```python
from core.utils.config_loader import load_config
config = load_config()  # Auto-finds config/config.yaml
db_url = config['timescaledb']['url']
```

**Tier 2: Pydantic** (when validation needed - data_service pattern):
```python
from services.data_service.config import get_settings
settings = get_settings()  # Validated, typed settings
db_url = settings.database.url
```

**When to use which**: Simple services → YAML. Complex services with validation → Pydantic. See `docs/guides/CORE_UTILITIES.md`.

### Environment Files

- **`.env`**: Docker-level variables (ports, feature flags)
- **`config/secrets.env`**: Sensitive credentials (API keys, passwords) - **gitignored**
- **`config/secrets.env.example`**: Template for required secrets
- **`config/config.yaml`**: Service configuration (database URLs, Kafka topics)

## Database Schema Patterns

### TimescaleDB Models

**Location**: `core/db/models.py`

**Base pattern**:
```python
from core.db.base import Base
from sqlalchemy import Column, Integer, String, TIMESTAMP

class MyModel(Base):
    __tablename__ = 'my_table'
    id = Column(Integer, primary_key=True)
    timestamp = Column(TIMESTAMP(timezone=True), nullable=False)
```

**Critical tables**:
- `tick_data`: Real-time tick data (hypertable)
- `ohlcv_data`: Multi-granularity candles (hypertable, composite PK: timestamp+instrument_token+interval)
- `token_records`: Broker access tokens (auth_service)

**Session management**: Use `core/db/session.py` for database sessions.

## Historical Data Loading

### Daily Scheduled Job

**Location**: `services/data_service/load/historical_batch_loader.py`

**Purpose**: Fetches previous trading day's data from Kite API and stores to MinIO in partitioned Parquet format.

**Partitioning Structure**: `historical/{symbol}/{year}/{month}/{week}/{day}/{hour}/{interval}.parquet`

**Schedule**: Runs daily at 4:30 PM IST (configurable via `HISTORICAL_SCHEDULE_TIME`)

**Configuration**:
```bash
# Environment variables
HISTORICAL_SYMBOLS=408065,884737,738561  # Comma-separated instrument tokens
HISTORICAL_INTERVALS=minute,5minute,15minute,60minute,day  # Kite API intervals
HISTORICAL_SCHEDULE_TIME=16:30  # HH:MM in IST
```

**Features**:
- ✅ **Incremental loading** - Checks if data exists before fetching
- ✅ **Comprehensive logging** - Logs all operations with timestamps
- ✅ **Configurable symbols** - Load from env, config, or defaults
- ✅ **Partitioned storage** - MinIO paths organized by Symbol/Year/Month/Week/Day/Hour
- ✅ **Rate limiting** - 0.5s delay between API calls
- ✅ **Error handling** - Continues on errors, logs failures

**Running the Scheduler**:
```bash
# Inside container (blocking - runs forever)
python /app/services/data_service/load/scheduler.py

# Test run immediately
python /app/services/data_service/load/scheduler.py --run-now

# Custom schedule time
python /app/services/data_service/load/scheduler.py --schedule-time 17:00
```

**Manual Execution**:
```bash
# Load specific date
python /app/services/data_service/load/historical_batch_loader.py --date 2025-10-18

# Custom symbols and intervals
python /app/services/data_service/load/historical_batch_loader.py \
  --symbols 408065,884737 \
  --intervals minute,5minute,day \
  --date 2025-10-18
```

## Live Data Streaming

### Real-Time Market Data Processing

**Location**: `services/data_service/load/realtime_stream_processor.py`

**Purpose**: Connects to Kite WebSocket and processes live market data in real-time.

**Data Flow**: WebSocket Ticks → TimescaleDB (raw ticks) → Candle Aggregation → TimescaleDB (OHLCV)

**Configuration**:
```bash
# Environment variables
LIVE_DATA_SYMBOLS=408065,884737,738561  # Comma-separated instrument tokens
LIVE_DATA_MODE=full  # WebSocket mode: ltp, quote, full
LIVE_DATA_INTERVALS=1m,5m,15m,1h,1d  # Candle intervals to generate
ENABLE_TICK_STORAGE=true  # Store raw ticks to DB
ENABLE_CANDLE_GENERATION=true  # Generate candles from ticks
```

**Features**:
- ✅ **Real-time tick storage** - Stores every tick to TimescaleDB
- ✅ **Multi-granularity candles** - Generates 1m, 5m, 15m, 1h, 1d from ticks
- ✅ **Auto-reconnection** - Handles connection drops with exponential backoff
- ✅ **Configurable symbols** - Load from env, config, or defaults
- ✅ **Multiple modes** - ltp (last price), quote (basic), full (with depth)
- ✅ **Comprehensive logging** - Logs ticks, candles, errors with stats

**Running Live Data**:
```bash
# Start with default configuration
python /app/services/data_service/load/realtime_stream_processor.py

# Custom symbols and mode
python /app/services/data_service/load/realtime_stream_processor.py \
  --symbols 408065,884737 \
  --mode full \
  --intervals 1m,5m,15m

# Disable tick storage (only generate candles)
python /app/services/data_service/load/realtime_stream_processor.py --no-tick-storage

# Disable candle generation (only store ticks)
python /app/services/data_service/load/realtime_stream_processor.py --no-candles
```

**WebSocket Modes**:
- `ltp`: Last traded price only (minimal data, fast)
- `quote`: OHLC + volume + buy/sell quantities
- `full`: Complete data including market depth

## Kafka Integration

**Bootstrap servers**: `kafka:9092` (internal Docker network)

**Topic naming**: 
- `market_data`: Raw tick data
- `candles_1m`, `candles_5m`, `candles_15m`, `candles_1h`, `candles_1d`: Granularity-specific candles

**Client selection**: Set `KAFKA_CLIENT=confluent` for confluent-kafka (preferred) or `kafka-python`.

**Enable/disable**: `ENABLE_KAFKA=true` in environment.

## Logging Standards

### Setup (once per service main.py)

```python
from core.utils.logger import setup_logging, get_logger

# Option 1: YAML config (recommended)
setup_logging(
    config_path="/app/config/logging.yaml",
    service_name="data_service",
    environment=os.getenv("ENVIRONMENT", "development")
)

# Option 2: Programmatic
setup_logging(
    service_name="data_service",
    log_level="INFO",
    json_logs=True  # JSON in production, human-readable in dev
)

logger = get_logger(__name__)
```

### Logging Conventions

```python
# ✅ Structured logging with context
logger.info("Processing tick", extra={"instrument": token, "price": tick.price})
logger.error("Failed to store candle", extra={"interval": "1m", "error": str(e)}, exc_info=True)

# ❌ Plain strings (harder to query)
logger.info(f"Processing tick {token}")
```

**Output**: Logs to `/logs/{service_name}.log` (rotating, 10MB max, 5 backups) AND console.

## Common Pitfalls to Avoid

1. **Don't create naive datetimes** - Always use `core.utils.time_utils.utc_now()` instead of `datetime.now()`
2. **Don't duplicate utilities** - Import from `core/utils/`, never copy to service directories
3. **Don't use `requests.get()` without timeout** - Always set `timeout=` parameter
4. **Don't forget to call `await container.cleanup()`** - Services need graceful shutdown
5. **Don't hardcode API URLs** - Use `config.yaml` or environment variables
6. **Don't skip error handling in async functions** - Wrap in try/except with proper exception types
7. **Don't commit `config/secrets.env`** - It's gitignored for a reason
8. **Don't query TimescaleDB without `ORDER BY timestamp DESC LIMIT`** - Hypertables can have millions of rows

## Key Files Reference

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Service orchestration, port mappings, dependencies |
| `config/config.yaml` | Service configuration (database, Kafka, MinIO) |
| `core/utils/logger.py` | **Single source** for logging (IST timezone, JSON support) |
| `core/utils/time_utils.py` | **Single source** for timezone-aware datetime operations |
| `services/data_service/main.py` | FastAPI app with lifespan management, DI container |
| `services/data_service/container.py` | Dependency injection pattern (AuthClient, processors, MinIO) |
| `services/data_service/processors/multi_granularity_aggregator.py` | Core tick→candle pipeline |
| `services/auth_service/main.py` | OAuth callback handling, token storage |
| `docs/architecture/PRODUCTION_READINESS.md` | Production deployment guide |
| `docs/MULTI_GRANULARITY_IMPLEMENTATION.md` | Data pipeline architecture |

## Quick Debugging Commands

```bash
# Check service health
curl http://localhost:8080/api/v1/health | jq

# View real-time logs
docker-compose logs -f --tail=100 data_service

# Check database connectivity
docker exec timescaledb pg_isready -U trader

# List MinIO buckets
docker exec minio mc ls minio/

# Check Kafka topics
docker exec kafka kafka-topics --list --bootstrap-server localhost:9092

# Restart stuck service
docker-compose restart data_service && docker-compose logs -f data_service

# Access Python shell in service
docker exec -it data_service python
```

## When Making Changes

### Adding a New Service

1. Create directory: `services/new_service/`
2. Add Dockerfile (can extend `services/base.Dockerfile`)
3. Add to `docker-compose.yml` extending `x-base-service`
4. Add health check endpoint: `/health` and `/api/v1/health`
5. Use `core/utils/logger.py` and `core/utils/time_utils.py`
6. Document in `docs/services/new_service/README.md`

### Adding Database Models

1. Define in `core/db/models.py` (shared) or `services/{service}/models.py` (service-specific)
2. Import `Base` from `core/db/base.py`
3. Create migration: `alembic revision -m "Add new table"`
4. Test migration in dev: `alembic upgrade head`
5. Add to production migration script: `services/data_service/db/migrate.py`

### Modifying Data Pipeline

1. **Understand granularity flow**: Changes to tick processing affect all downstream candles
2. **Test with demo**: Run `demo_multi_granularity.py` to verify tick→candle aggregation
3. **Check all storage layers**: TimescaleDB, MinIO, Kafka all need consistent schemas
4. **Update processors**: Both `MultiGranularityProcessor` (live) and `BatchMultiGranularityProcessor` (historical)
5. **Verify via API**: Query `/api/ohlcv?interval=1m&limit=10` to confirm changes

---

**Last Updated**: October 19, 2025  
**Platform Status**: ✅ Operational (auth+data services running, 1901+ candles stored)  
**Next Steps**: Enable live data streaming or run historical backfill
