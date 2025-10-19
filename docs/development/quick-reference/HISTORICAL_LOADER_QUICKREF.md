# Historical Data Loader - Quick Reference

## 🚀 Quick Start

### Run Scheduler (Production)
```bash
docker exec -d data_service python /app/services/data_service/load/scheduler.py
```

### Manual Load (Testing)
```bash
# Yesterday's data
docker exec data_service python /app/services/data_service/load/historical_data.py

# Specific date
docker exec data_service python /app/services/data_service/load/historical_data.py --date 2025-10-18
```

### Test Immediately
```bash
docker exec data_service python /app/services/data_service/load/scheduler.py --run-now
```

---

## ⚙️ Configuration

```bash
# Environment variables
HISTORICAL_SYMBOLS=408065,884737,738561           # Instrument tokens
HISTORICAL_INTERVALS=minute,5minute,day           # Kite API intervals
HISTORICAL_SCHEDULE_TIME=16:30                    # HH:MM in IST
```

---

## 📂 Storage Path

```
market-data/historical/{symbol}/{year}/{month}/{week}/{day}/{hour}/{interval}.parquet
```

**Example**: `historical/NIFTY50/2025/10/42/18/14/1m.parquet`

---

## 🔍 Check Data

```bash
# List stored data
docker exec minio mc ls minio/market-data/historical/NIFTY50/ --recursive

# Check logs
docker logs -f historical_data_scheduler

# Test suite
docker exec data_service python /app/test_historical_loader.py
```

---

## 📊 Key Features

- ✅ **Scheduled**: Runs daily at 4:30 PM IST
- ✅ **Incremental**: Skips existing data
- ✅ **Partitioned**: Symbol/Year/Month/Week/Day/Hour
- ✅ **Configurable**: Symbols and intervals via env
- ✅ **Resilient**: Continues on errors
- ✅ **Logged**: Comprehensive operation logs

---

## 🆘 Troubleshooting

| Problem | Solution |
|---------|----------|
| Token error | Regenerate at http://localhost:8018 |
| MinIO error | `docker-compose up minio` |
| No scheduler | `docker ps \| grep scheduler` |
| Check logs | `docker logs historical_data_scheduler` |

---

## 📖 Full Documentation

- **User Guide**: `services/data_service/load/README.md`
- **Implementation**: `docs/services/data_service/HISTORICAL_DATA_LOADER.md`
- **AI Instructions**: `.github/copilot-instructions.md`
