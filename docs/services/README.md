# Services Documentation

This directory contains documentation for all microservices in the AlgoTrading platform.

## 📚 Service Documentation Index

### 🔐 Auth Service (`auth_service/`)

Authentication and authorization service handling OAuth 2.0 integration with Zerodha Kite.

#### Core Documentation
- [**README.md**](auth_service/README.md) - Auth service overview and features
- [**SETUP_GUIDE.md**](auth_service/SETUP_GUIDE.md) - Complete setup and configuration guide

#### Detailed Documentation
- [**01-architecture.md**](auth_service/01-architecture.md) - Service architecture and design patterns
- [**02-token-management.md**](auth_service/02-token-management.md) - Token lifecycle and management
- [**03-api-reference.md**](auth_service/03-api-reference.md) - Complete API reference
- [**04-development.md**](auth_service/04-development.md) - Development guidelines and workflows

#### Additional Resources
- [**restructuring_plan.md**](auth_service/restructuring_plan.md) - Service restructuring notes
- [**scripts_README.md**](auth_service/scripts_README.md) - Scripts documentation

**Tech Stack**: FastAPI, PostgreSQL, Redis, Kite Connect API  
**Port**: 8018  
**Key Features**: 
- OAuth 2.0 flow with Zerodha
- Secure token encryption (AES-256)
- Session management
- Token caching and refresh

---

### 📊 Data Service (`data_service/`)

Market data streaming, storage, and processing service.

#### Core Documentation
- [**README.md**](data_service/README.md) - Data service overview
- [**QUICKSTART.md**](data_service/QUICKSTART.md) - Quick start guide

#### Status Reports
- [**CURRENT_STATUS.md**](data_service/CURRENT_STATUS.md) - Current implementation status
- [**SERVICE_STATUS.md**](data_service/SERVICE_STATUS.md) - Service health and status
- [**FINAL_STATUS.md**](data_service/FINAL_STATUS.md) - Final implementation status
- [**IMPLEMENTATION_COMPLETE.md**](data_service/IMPLEMENTATION_COMPLETE.md) - Implementation completion report
- [**IMPLEMENTATION_SUMMARY.md**](data_service/IMPLEMENTATION_SUMMARY.md) - Summary of implementation

**Tech Stack**: FastAPI, TimescaleDB, Kafka, MinIO, WebSocket  
**Port**: 8080  
**Key Features**:
- Live data streaming via WebSocket
- Historical data fetching
- Dual storage (TimescaleDB + MinIO)
- Kafka event streaming
- Production-ready with DI, health checks, error handling

---

## 🏗️ Service Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        API Gateway / Load Balancer              │
└─────────────────────────────────────────────────────────────────┘
                                  │
                 ┌────────────────┼────────────────┐
                 ▼                ▼                ▼
         ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
         │ Auth Service │  │ Data Service │  │Risk Service  │
         │  Port 8018   │  │  Port 8080   │  │  Port 8082   │
         └──────────────┘  └──────────────┘  └──────────────┘
                 │                │                │
                 ▼                ▼                ▼
         ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
         │  PostgreSQL  │  │ TimescaleDB  │  │  PostgreSQL  │
         │    Redis     │  │    MinIO     │  │              │
         └──────────────┘  │    Kafka     │  └──────────────┘
                           └──────────────┘
                                  │
                 ┌────────────────┼────────────────┐
                 ▼                ▼                ▼
         ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
         │  Execution   │  │  Strategy    │  │  Monitoring  │
         │   Service    │  │   Service    │  │   Service    │
         │  Port 8083   │  │  Port 8084   │  │ Prometheus   │
         └──────────────┘  └──────────────┘  │   Grafana    │
                                              └──────────────┘
```

## 🔄 Service Communication

### Auth Service Integration
All services communicate with Auth Service to obtain access tokens:

```python
from services.data_service.extraction.auth_client import AuthClient

auth_client = AuthClient(auth_service_url="http://localhost:8018")
token = await auth_client.get_access_token()
```

### Event Streaming (Kafka)
Services publish and consume events via Kafka:
- `market_data` - Live tick data
- `orders` - Order events
- `trades` - Trade execution events
- `positions` - Position updates

### Data Flow
1. **Auth Service** → Provides access tokens to other services
2. **Data Service** → Fetches and stores market data
3. **Strategy Service** → Consumes market data, generates signals
4. **Execution Service** → Places orders based on signals
5. **Risk Service** → Monitors positions and enforces risk limits
6. **Monitoring Service** → Collects metrics and alerts

## 🚀 Quick Start

### Starting Individual Services

```bash
# Auth Service
cd services/auth_service
docker-compose up -d

# Data Service
cd services/data_service
docker-compose up -d
```

### Starting All Services

```bash
# From project root
docker-compose up -d
```

### Accessing Services

- **Auth Service**: http://localhost:8018
  - Swagger Docs: http://localhost:8018/docs
  - Health: http://localhost:8018/health

- **Data Service**: http://localhost:8080
  - Swagger Docs: http://localhost:8080/docs
  - Health: http://localhost:8080/api/v1/health
  - Readiness: http://localhost:8080/api/v1/ready

## 📝 Development Guidelines

### Adding a New Service

1. Create service directory under `services/`
2. Follow microservice template structure
3. Implement health check endpoints
4. Add service to docker-compose.yml
5. Document in this README
6. Create service-specific documentation

### Service Standards

All services must implement:
- ✅ Health check endpoint (`/health` or `/api/v1/health`)
- ✅ Readiness probe (`/api/v1/ready`)
- ✅ Liveness probe (`/api/v1/live`)
- ✅ Prometheus metrics endpoint (`/metrics`)
- ✅ OpenAPI/Swagger documentation (`/docs`)
- ✅ Structured logging
- ✅ Graceful shutdown handling
- ✅ Error handling middleware
- ✅ Configuration management

### Code Organization

```
services/
├── service_name/
│   ├── api/              # API routes
│   ├── core/             # Business logic
│   ├── db/               # Database models
│   ├── config.py         # Configuration
│   ├── exceptions.py     # Custom exceptions
│   ├── container.py      # Dependency injection
│   ├── middleware.py     # Middlewares
│   ├── main.py           # Application entry point
│   └── Dockerfile        # Docker configuration
```

## 🧪 Testing

Each service should include:
- Unit tests for business logic
- Integration tests for API endpoints
- End-to-end tests for critical workflows

```bash
# Run tests for a service
cd services/service_name
pytest tests/
```

## 📊 Monitoring

All services expose Prometheus metrics at `/metrics`:
- Request count and latency
- Error rates
- Custom business metrics
- Dependency health

Access monitoring:
- **Grafana**: http://localhost:3000
- **Prometheus**: http://localhost:9090

## 🔒 Security

- All services use OAuth 2.0 via Auth Service
- Secrets managed via environment variables
- Database credentials encrypted
- API tokens cached with TTL
- HTTPS/TLS in production

## 📖 Related Documentation

- [Production Readiness](../PRODUCTION_READINESS.md) - Overall platform production readiness
- [Auth Best Practices](../auth_best_practices.md) - Security guidelines
- [Logging Guide](../logging_guide.md) - Logging standards
- [Time Handling](../time_handling.md) - Timezone management

---

**Last Updated**: October 18, 2025  
**Active Services**: Auth Service, Data Service  
**In Development**: Risk Service, Execution Service, Strategy Service
