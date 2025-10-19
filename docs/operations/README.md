# Operations Documentation

Operations guides, testing procedures, and troubleshooting documentation for the AlgoTrading platform.

---

## 📂 Contents

### [Testing](./testing/)
Verification reports, test results, and testing procedures
- System verification reports
- Historical data test analysis
- Project verification checklists

### [Troubleshooting](./troubleshooting/)
Status reports and debugging guides for operational issues
- Data extraction status
- Live data streaming diagnostics
- Database health reports

---

## 🔧 Quick Links

### Running Tests
- [Verification Report](./testing/VERIFICATION_REPORT.md) - Complete system verification
- [Historical Data Tests](./testing/HISTORICAL_DATA_TEST_ANALYSIS.md) - Historical loader tests
- [Project Verification](./testing/PROJECT_VERIFICATION.md) - Project-wide verification

### Troubleshooting
- [Data Extraction Status](./troubleshooting/DATA_EXTRACTION_STATUS.md) - Check data flow
- [Live Data Status](./troubleshooting/LIVE_DATA_STATUS.md) - WebSocket diagnostics
- [TimescaleDB Status](./troubleshooting/TIMESCALEDB_STATUS_REPORT.md) - Database health

---

## 🚀 Common Operations

### Check System Health
```bash
# Verify all services running
docker-compose ps

# Check data service health
curl http://localhost:8080/api/v1/health

# Monitor heartbeat
monitor_heartbeat.bat
```

### Run Tests
```bash
# Run verification
python verify_system.py

# Check historical data
docker exec data_service python /app/test_historical_data.py
```

### Troubleshoot Issues
1. Check service logs: `docker logs data_service`
2. Verify database: `docker exec timescaledb psql -U trader -d trading`
3. Test connectivity: `docker exec data_service ping timescaledb`

---

## 📚 Related Documentation

- [Architecture](../architecture/) - System architecture and design
- [Services](../services/) - Service-specific documentation
- [Guides](../guides/) - Development and usage guides
- [Reports](../reports/) - Status reports and summaries
