# Data Availability Report
**AlgoTrading Platform**  
**Date:** October 18, 2025  
**Report Generated:** 23:39 IST

---

## Executive Summary

This report verifies the availability and status of both **live streaming data** and **historical data** in the AlgoTrading platform.

### Quick Status
| Data Type | Status | Details |
|-----------|--------|---------|
| **Live Data Streaming** | ⚠️ **Configured but Not Active** | Worker enabled but authentication failing |
| **Historical Data** | ❌ **Not Available** | No data stored, backfill not executed |
| **Database** | ✅ **Ready** | TimescaleDB healthy, tables created |
| **Storage** | ✅ **Ready** | MinIO operational, bucket created |
| **APIs** | ✅ **Ready** | Data retrieval endpoints available |

---

## 1. Live Data Streaming

### Configuration Status
```json
{
  "workers_enabled": {
    "live_data": true,
    "historical_data": false
  }
}
```

### Current Status: ⚠️ **NOT OPERATIONAL**

**Issue:** Live data worker cannot connect to Kite WebSocket API due to authentication failure.

**Error Log:**
```
ERROR | services.data_service.extraction.live_data | Failed to fetch access token from auth service
ERROR | data_service.workers | Error in live data worker: Failed to fetch access token
WARNING | data_service.workers | WebSocket disconnected - Will attempt to reconnect
```

**Root Cause:**
- Auth service is not providing valid Kite Connect access tokens
- Auth service status shows "No token available"
- Without valid token, WebSocket connection to Kite API cannot be established

**Requirements for Live Data:**
1. ✅ Kite Connect API credentials (configured)
2. ❌ Valid access token from auth service
3. ✅ WebSocket worker enabled
4. ✅ 7 instruments configured for streaming (tokens: 408065, 884737, 738561, 779521, 340481, 256265, 264969)

**To Enable Live Data:**
1. Configure valid Kite Connect API credentials in auth service
2. Generate access token through Kite Connect login flow
3. Restart data service - worker will automatically connect

---

## 2. Historical Data

### Configuration Status
```json
{
  "workers_enabled": {
    "historical_data": false
  }
}
```

### Current Status: ❌ **NO DATA AVAILABLE**

**Database Status:**
```sql
Table          | Record Count | Oldest Record | Newest Record
---------------|--------------|---------------|---------------
tick_data      | 0            | NULL          | NULL
ohlcv_data     | 0            | NULL          | NULL
instrument_master | 0         | NULL          | NULL
```

**MinIO Storage:**
```
Bucket: market-data
Status: Empty
Path: /ohlcv/ - No data files
```

**Available Tools:**
- ✅ Backfill script: `/services/data_service/backfill_historical_data.py`
- ✅ Historical data fetcher configured
- ✅ MinIO storage ready
- ✅ TimescaleDB tables created

**Backfill Configuration:**
- **Instruments:** 7 tokens configured
- **Time Range:** 5 years of historical data
- **Intervals:** day, 60minute, 15minute
- **Storage Structure:** `ohlcv/YYYY/MM/WEEK/DD/HH/interval/instrument_token.parquet`

**To Load Historical Data:**

**Option 1: Run Backfill Script (Recommended)**
```bash
# Execute inside data_service container
docker exec -it data_service python /app/services/data_service/backfill_historical_data.py
```

**Option 2: Enable Historical Worker**
```yaml
# In docker-compose.yml or environment variables
DATA_SERVICE_WORKERS_HISTORICAL_FETCH: "true"
```

**Option 3: API Trigger**
```bash
curl -X POST http://localhost:8080/api/historical/fetch \
  -H "Content-Type: application/json" \
  -d '{"instrument_tokens": [408065, 884737], "years": 5}'
```

---

## 3. Data APIs

### API Endpoints Status: ✅ **OPERATIONAL**

**Base URL:** `http://localhost:8080/api`

### Available Endpoints:

#### Real-time Data APIs
| Endpoint | Method | Status | Purpose |
|----------|--------|--------|---------|
| `/ticks/latest` | GET | ✅ Ready | Get latest tick for instruments |
| `/ticks/history` | GET | ✅ Ready | Get historical tick data |
| `/stats` | GET | ✅ Working | Get data statistics |

**Example:**
```bash
# Get latest ticks
curl "http://localhost:8080/api/ticks/latest?instrument_tokens=408065,884737"

# Get tick history
curl "http://localhost:8080/api/ticks/history?instrument_token=408065&limit=100"

# Get statistics
curl "http://localhost:8080/api/stats"
```

**Current Stats Response:**
```json
{
    "tick_count": 0,
    "ohlcv_count": 0,
    "instrument_count": 0,
    "latest_tick_time": null,
    "metadata": {},
    "timestamp": "2025-10-18T18:08:57"
}
```

#### OHLCV/Candle Data APIs
| Endpoint | Method | Status | Purpose |
|----------|--------|--------|---------|
| `/ohlcv` | GET | ✅ Ready | Get OHLCV candle data |

**Example:**
```bash
# Get daily candles for last year
curl "http://localhost:8080/api/ohlcv?instrument_token=408065&interval=1d"

# Get 15-minute candles
curl "http://localhost:8080/api/ohlcv?instrument_token=408065&interval=15m&limit=500"
```

#### Instrument APIs
| Endpoint | Method | Status | Purpose |
|----------|--------|--------|---------|
| `/instruments` | GET | ✅ Ready | Search instruments |
| `/instruments/{token}` | GET | ✅ Ready | Get instrument details |

#### Control APIs
| Endpoint | Method | Status | Purpose |
|----------|--------|--------|---------|
| `/websocket/subscribe` | POST | ✅ Ready | Subscribe to live instruments |
| `/websocket/unsubscribe` | POST | ✅ Ready | Unsubscribe from instruments |
| `/historical/fetch` | POST | ✅ Ready | Trigger historical data fetch |

---

## 4. Infrastructure Status

### Database: TimescaleDB
```
Status: ✅ HEALTHY
Connection: postgresql://trader:***@timescaledb:5432/trading
Response Time: 3.43 ms
Tables Created: 4 (tick_data, ohlcv_data, instrument_master, data_service_metadata)
```

### Object Storage: MinIO
```
Status: ✅ HEALTHY
Endpoint: http://minio:9000
Bucket: market-data
Response Time: 9.70 ms
Storage Used: 0 B (empty)
```

### Message Queue: Kafka
```
Status: ✅ HEALTHY
Broker: kafka:9092
Topics: marketdata
Consumer Groups: Active
```

### Auth Service
```
Status: ⚠️ DEGRADED
URL: http://auth_service:8018
Response Time: 8.50 ms
Token Available: No
```

---

## 5. Data Flow Architecture

### Live Data Flow (When Active):
```
Kite WebSocket API
    ↓ (WebSocket connection with access token)
LiveDataWorker
    ↓ (Process ticks)
TickProcessor
    ├→ TimescaleDB (tick_data table)
    ├→ Kafka (marketdata topic)
    └→ MinIO (parquet files)
```

### Historical Data Flow:
```
Kite Historical API
    ↓ (HTTP requests with access token)
HistoricalDataFetcher
    ↓ (Fetch OHLCV data)
OHLCVProcessor
    ├→ TimescaleDB (ohlcv_data table)
    └→ MinIO (partitioned parquet: /ohlcv/YYYY/MM/...)
```

---

## 6. Recommendations

### Immediate Actions:

1. **Fix Auth Service** ⚠️ HIGH PRIORITY
   - Configure Kite Connect API credentials
   - Generate valid access token
   - This blocks both live and historical data

2. **Run Historical Backfill** 📊 RECOMMENDED
   ```bash
   docker exec -it data_service python /app/services/data_service/backfill_historical_data.py
   ```
   - Will fetch 5 years of data for 7 instruments
   - Supports resume if interrupted
   - Shows progress with ETA

3. **Enable Historical Worker** (Optional)
   - Set `DATA_SERVICE_WORKERS_HISTORICAL_FETCH=true`
   - Enables automated daily updates at 4 PM IST

### Monitoring:

**Check Data Growth:**
```bash
# Monitor database
docker exec timescaledb psql -U trader -d trading -c "SELECT COUNT(*) FROM tick_data;"

# Monitor storage
docker exec minio mc du minio/market-data

# Check API stats
curl http://localhost:8080/api/stats
```

**Check Worker Status:**
```bash
# View logs
docker compose logs data_service --tail 100

# Check health
curl http://localhost:8080/api/v1/health
```

---

## 7. Summary

### What's Working ✅
- ✅ All infrastructure services running
- ✅ Database ready with proper schema
- ✅ MinIO storage operational
- ✅ Kafka message broker active
- ✅ API endpoints functional
- ✅ Data workers configured

### What's Not Working ❌
- ❌ No live data (auth token missing)
- ❌ No historical data (backfill not executed)
- ❌ Auth service not providing tokens

### Next Steps
1. **Configure Kite Connect credentials** in auth service
2. **Run historical backfill script** to populate 5 years of data
3. **Restart data service** to activate live streaming
4. **Verify data flow** using API endpoints

---

## Appendix: Quick Commands

### Check Data Availability
```bash
# Database records
docker exec timescaledb psql -U trader -d trading -c "SELECT 'tick_data' as table, COUNT(*) as records FROM tick_data UNION ALL SELECT 'ohlcv_data', COUNT(*) FROM ohlcv_data;"

# MinIO storage
docker exec minio mc ls minio/market-data/ohlcv/ --recursive

# API stats
curl http://localhost:8080/api/stats | python -m json.tool
```

### Start Data Collection
```bash
# Run backfill (5 years historical data)
docker exec -it data_service python /app/services/data_service/backfill_historical_data.py

# Check progress
docker compose logs data_service -f
```

### Test APIs
```bash
# Health check
curl http://localhost:8080/api/v1/health

# Get stats
curl http://localhost:8080/api/stats

# Get latest ticks (when data available)
curl "http://localhost:8080/api/ticks/latest?instrument_tokens=408065"
```

---

**Report End**  
**Generated by:** AlgoTrading Platform Data Verification System  
**Contact:** System Administrator
