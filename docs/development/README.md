# Development Documentation

Development guides, refactoring history, and quick references for contributors.

---

## 📂 Contents

### [Refactoring](./refactoring/)
History of major refactoring efforts and code reorganizations
- File rename operations
- Utility consolidation
- Code structure improvements

### [Quick Reference](./quick-reference/)
Quick reference guides and cheat sheets for common tasks
- Historical data loader commands
- API endpoint references
- Common workflows

---

## 🛠️ Development Setup

### Prerequisites
- Docker Desktop
- Python 3.12+
- Git
- VS Code (recommended)

### Quick Start
```bash
# Clone repository
git clone https://github.com/upsurge96-bit/AlgoTrading_v1.0.git
cd AlgoTrading_v1

# Start all services
docker-compose up --build -d

# Check health
docker-compose ps
curl http://localhost:8080/api/v1/health
```

---

## 📝 Development Guidelines

### Code Style
- Follow PEP 8 for Python code
- Use type hints for function signatures
- Document all public APIs
- Write docstrings for modules and classes

### Import Standards
```python
# ✅ CORRECT: Use centralized utilities
from core.utils.logger import get_logger
from core.utils.time_utils import utc_now

# ❌ WRONG: Don't create duplicates
from services.my_service.logger import get_logger
```

### Timezone Handling
```python
# ✅ CORRECT: Always use timezone-aware datetimes
from core.utils.time_utils import utc_now
timestamp = utc_now()  # Returns datetime with UTC timezone

# ❌ WRONG: Naive datetimes
from datetime import datetime
timestamp = datetime.now()  # Missing timezone!
```

### Logging
```python
# ✅ CORRECT: Structured logging
from core.utils.logger import get_logger
logger = get_logger(__name__)
logger.info("Processing tick", extra={"instrument": token, "price": tick.price})

# ❌ WRONG: Plain strings
logger.info(f"Processing tick {token}")
```

---

## 🔄 Common Development Tasks

### Adding a New Service
1. Create directory: `services/new_service/`
2. Add Dockerfile extending `services/base.Dockerfile`
3. Update `docker-compose.yml`
4. Add health check endpoint: `/health`
5. Use centralized utilities from `core/`
6. Document in `docs/services/new_service/README.md`

### Adding a Database Model
1. Define in `core/db/models.py` (shared) or `services/{service}/models.py`
2. Create migration: `alembic revision -m "Add new table"`
3. Test in dev environment
4. Update documentation

### Modifying Data Pipeline
1. Understand granularity flow (ticks → 1m → 5m → 15m → 1h → 1d)
2. Test with demo: `demo_multi_granularity.py`
3. Verify all storage layers (TimescaleDB, MinIO, Kafka)
4. Update both live and batch processors

---

## 🧪 Testing

### Run Tests
```bash
# All tests
pytest

# Specific test file
pytest tests/test_core_utilities.py

# With coverage
pytest --cov=services --cov=core
```

### Manual Testing
```bash
# Test historical loader
docker exec data_service python /app/services/data_service/load/historical_batch_loader.py --date 2025-10-17

# Test live streaming
docker exec data_service python /app/services/data_service/load/realtime_stream_processor.py --symbols 408065
```

---

## 📚 Key Documentation

### Architecture
- [System Architecture](../architecture/README.md)
- [Multi-Granularity Implementation](../architecture/MULTI_GRANULARITY_IMPLEMENTATION.md)
- [Production Readiness](../architecture/PRODUCTION_READINESS.md)

### Guides
- [Core Utilities](../guides/CORE_UTILITIES.md)
- [Logging Guide](../guides/logging/)
- [Time Handling](../guides/time-handling/)
- [Authentication](../guides/authentication/)

### Services
- [Data Service](../services/data_service/)
- [Auth Service](../services/auth_service/)

---

## 🔧 Troubleshooting Development Issues

### Import Errors
- Ensure you're importing from `core/` for shared utilities
- Check `sys.path` includes project root
- Verify Docker volumes are mounted correctly

### Database Connection Issues
- Check `config/secrets.env` has correct credentials
- Verify TimescaleDB is running: `docker-compose ps`
- Test connection: `docker exec timescaledb pg_isready -U trader`

### Hot Reload Not Working
- Ensure volumes are mounted in `docker-compose.yml`
- Check file permissions
- Restart service: `docker-compose restart data_service`

---

## 🚀 Deployment

### Build for Production
```bash
# Build all images
docker-compose build

# Tag for registry
docker tag algotrading_v1-data_service:latest your-registry/data_service:v1.0

# Push to registry
docker push your-registry/data_service:v1.0
```

### Environment Configuration
- **Development**: `.env` + `config/secrets.env`
- **Production**: Use environment variables or secrets management
- **Never commit**: `config/secrets.env`

---

## 📖 Additional Resources

- [GitHub Copilot Instructions](../../.github/copilot-instructions.md)
- [Refactoring History](./refactoring/)
- [Quick References](./quick-reference/)
- [Operations Guides](../operations/)
