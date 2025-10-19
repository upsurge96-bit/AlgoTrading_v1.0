# Testing Documentation

Test reports, verification procedures, and quality assurance documentation.

---

## 📋 Test Reports

### System Verification
- **[VERIFICATION_REPORT.md](./VERIFICATION_REPORT.md)** - Latest system verification results
  - Service health checks
  - Database connectivity
  - API endpoint tests
  - Data flow verification

### Historical Data Testing
- **[HISTORICAL_DATA_TEST_ANALYSIS.md](./HISTORICAL_DATA_TEST_ANALYSIS.md)** - Historical loader test results
  - MinIO storage validation
  - API extraction tests
  - Partitioning verification
  - Performance metrics

### Project Verification
- **[PROJECT_VERIFICATION.md](./PROJECT_VERIFICATION.md)** - Complete project verification checklist
  - Module imports
  - Configuration validation
  - Service integration tests
  - End-to-end workflows

---

## 🧪 Running Tests

### Automated System Verification
```bash
# Run complete verification
python verify_system.py

# Quick health check
docker-compose ps
curl http://localhost:8080/api/v1/health
```

### Manual Testing

#### Database Tests
```bash
# Connect to TimescaleDB
docker exec -it timescaledb psql -U trader -d trading

# Check tick data
SELECT COUNT(*) FROM tick_data;

# Check OHLCV data
SELECT interval, COUNT(*) FROM ohlcv_data GROUP BY interval;
```

#### Data Loading Tests
```bash
# Test historical loader
docker exec data_service python /app/services/data_service/load/historical_batch_loader.py --date 2025-10-17

# Test live streaming
docker exec data_service python /app/services/data_service/load/realtime_stream_processor.py --symbols 408065
```

---

## ✅ Test Checklist

### Pre-Deployment
- [ ] All services start without errors
- [ ] Database migrations applied
- [ ] WebSocket connects successfully
- [ ] Historical data loads correctly
- [ ] Live data streams properly
- [ ] MinIO storage working
- [ ] Kafka topics created
- [ ] Logs are readable

### Post-Deployment
- [ ] Health endpoints responding
- [ ] Data persisting to database
- [ ] No memory leaks
- [ ] Logs show no errors
- [ ] Market hours detection working
- [ ] Heartbeat monitoring active

---

## 📊 Test Metrics

| Metric | Target | Current | Status |
|--------|--------|---------|--------|
| Service Uptime | 99.9% | - | ⏳ |
| API Response Time | <100ms | - | ⏳ |
| Data Ingestion Rate | >1000 ticks/sec | - | ⏳ |
| Database Write Latency | <10ms | - | ⏳ |
| Storage Efficiency | >80% | - | ⏳ |

---

## 🐛 Known Issues

See [Troubleshooting](../troubleshooting/) for current known issues and workarounds.

---

## 📚 Related Documentation

- [Troubleshooting](../troubleshooting/) - Diagnostic guides
- [Services](../../services/) - Service documentation
- [Architecture](../../architecture/) - System design
