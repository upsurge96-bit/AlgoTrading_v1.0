# AlgoTrading Platform Documentation

Welcome to the comprehensive documentation for the AlgoTrading platform. This documentation is organized into logical sections for easy navigation.

## 📁 Documentation Structure

```
docs/
├── README.md                       # This file
├── architecture/                   # Architecture & Design
├── guides/                         # How-to Guides
│   ├── authentication/            # Auth & Security
│   ├── logging/                   # Logging System
│   └── time-handling/             # Time & Timezone
├── services/                       # Service Documentation
│   ├── auth_service/              # Auth Service
│   └── data_service/              # Data Service
└── status-reports/                # Implementation Reports
```

## 🏗️ Architecture & Design

Production-ready architecture, design patterns, and system overview.

- [**PRODUCTION_READINESS.md**](architecture/PRODUCTION_READINESS.md) - Production readiness summary with complete architecture overview, dependency injection, error handling, health checks, and deployment guidelines

## 📖 Guides

### ⚙️ Core Utilities ([guides/CORE_UTILITIES.md](guides/CORE_UTILITIES.md))
**NEW!** Centralized logging and configuration - the foundation for all services.
- How to use `core.utils.logger` for consistent logging
- How to use `core.utils.config_loader` for simple YAML configs
- Migration guide from deprecated utilities
- When to use Pydantic config vs simple config

### 🔐 Authentication & Security ([guides/authentication/](guides/authentication/))
- [**auth_best_practices.md**](guides/authentication/auth_best_practices.md) - Security best practices for authentication
- [**auth_service_cleanup.md**](guides/authentication/auth_service_cleanup.md) - Auth service cleanup and refactoring notes
- [**auth_service_learnings.md**](guides/authentication/auth_service_learnings.md) - Lessons learned from implementation
- [**READY_FOR_LOGIN.md**](guides/authentication/READY_FOR_LOGIN.md) - OAuth setup and login readiness guide

### 📊 Logging System ([guides/logging/](guides/logging/))
- [**logging_system.md**](guides/logging/logging_system.md) - Comprehensive logging system overview
- [**logging_guide.md**](guides/logging/logging_guide.md) - How to use the logging system
- [**logging_standardization.md**](guides/logging/logging_standardization.md) - Logging standards and conventions
- [**logging_refactoring_completion.md**](guides/logging/logging_refactoring_completion.md) - Refactoring completion report
- [**logging_future_improvements.md**](guides/logging/logging_future_improvements.md) - Future improvements roadmap
- [**logger_migration_guide.md**](guides/logging/logger_migration_guide.md) - Migration guide for legacy code

### ⏰ Time Handling ([guides/time-handling/](guides/time-handling/))
- [**time_handling.md**](guides/time-handling/time_handling.md) - Time handling strategies and timezone management
- [**time_handling_interview.md**](guides/time-handling/time_handling_interview.md) - In-depth Q&A on time handling

## 🔧 Services

Microservice-specific documentation with API references and setup guides.

- [**services/**](services/README.md) - Services hub with architecture diagrams
  - [**auth_service/**](services/auth_service/README.md) - OAuth 2.0, token management, session handling
  - [**data_service/**](services/data_service/README.md) - Market data streaming, storage, and processing

## 📊 Status Reports

Implementation milestones, success reports, and critical fixes.

- [**CRITICAL_FIX_APPLIED.md**](status-reports/CRITICAL_FIX_APPLIED.md) - Critical OAuth configuration fix
- [**HISTORICAL_DATA_TEST_SUCCESS.md**](status-reports/HISTORICAL_DATA_TEST_SUCCESS.md) - Historical data testing results
- [**SUCCESS_LIVE_DATA_STREAMING.md**](status-reports/SUCCESS_LIVE_DATA_STREAMING.md) - Live data streaming success

## 🏗️ Platform Architecture

The AlgoTrading platform consists of several microservices:

### Core Services
1. **Auth Service** (Port 8018) - OAuth 2.0 integration, token management
2. **Data Service** (Port 8080) - Market data streaming and storage
3. **Risk Service** (Port 8082) - Position and portfolio risk management
4. **Execution Service** (Port 8083) - Order placement and execution
5. **Strategy Service** (Port 8084) - Strategy backtesting and execution

### Infrastructure
- **Database**: PostgreSQL 14 + TimescaleDB (time-series data)
- **Message Queue**: Apache Kafka (event streaming)
- **Object Storage**: MinIO (S3-compatible archival)
- **Cache**: Redis (session and token caching)
- **Monitoring**: Prometheus + Grafana + Alertmanager

See [architecture/PRODUCTION_READINESS.md](architecture/PRODUCTION_READINESS.md) for detailed architecture diagrams.

## 🚀 Quick Start

### For Developers

1. **Setup Environment**
   ```bash
   cp config/secrets.env.example config/secrets.env
   # Edit secrets.env with your credentials
   ```

2. **Start Services**
   ```bash
   docker-compose up -d
   ```

3. **Setup Authentication**
   - Follow [guides/authentication/READY_FOR_LOGIN.md](guides/authentication/READY_FOR_LOGIN.md)

4. **Check Logging**
   - Read [guides/logging/logging_guide.md](guides/logging/logging_guide.md)

### For Service Development

- **Auth Service**: See [services/auth_service/SETUP_GUIDE.md](services/auth_service/SETUP_GUIDE.md)
- **Data Service**: See [services/data_service/QUICKSTART.md](services/data_service/QUICKSTART.md)

## 🔍 Finding Documentation

### By Topic
- **Security & Auth**: [guides/authentication/](guides/authentication/)
- **Logging**: [guides/logging/](guides/logging/)
- **Time & Timezones**: [guides/time-handling/](guides/time-handling/)
- **Architecture**: [architecture/](architecture/)
- **Services**: [services/](services/)

### By Service
Navigate to [services/](services/) and select the service you need:
- Auth Service - Complete OAuth flow, token encryption, session management
- Data Service - WebSocket streaming, historical data, dual storage

### Quick Links
- 📘 [Production Deployment](architecture/PRODUCTION_READINESS.md)
- ⚙️ [Core Utilities Guide](guides/CORE_UTILITIES.md) - **START HERE**
- 🔐 [Authentication Setup](guides/authentication/READY_FOR_LOGIN.md)
- 📊 [Logging Best Practices](guides/logging/logging_guide.md)
- ⏰ [Time Handling Guide](guides/time-handling/time_handling.md)
- 🎯 [Latest Success Report](status-reports/SUCCESS_LIVE_DATA_STREAMING.md)

## 📝 Contributing to Documentation

### Adding New Documentation

1. **Choose the right location**:
   - Architecture docs → `architecture/`
   - How-to guides → `guides/<topic>/`
   - Service docs → `services/<service_name>/`
   - Status reports → `status-reports/`

2. **Follow naming conventions**:
   - Use descriptive names: `SERVICE_STATUS.md` not `status.md`
   - Use uppercase for important: `README.md`, `SETUP_GUIDE.md`
   - Use lowercase for detailed: `01-architecture.md`
   - Use hyphens for multi-word: `auth-best-practices.md`

3. **Update indexes**:
   - Add links to this README
   - Update relevant section READMEs

### Documentation Standards

- ✅ Use clear, descriptive headings
- ✅ Include code examples where applicable
- ✅ Add diagrams for complex concepts
- ✅ Keep documentation in sync with code
- ✅ Use emoji icons for visual navigation
- ✅ Link to related documentation

## �️ Development Stack

- **Python**: 3.12+
- **Framework**: FastAPI
- **Database**: PostgreSQL 14 + TimescaleDB
- **Message Queue**: Apache Kafka
- **Object Storage**: MinIO
- **Monitoring**: Prometheus + Grafana
- **Container**: Docker + Docker Compose

## 📊 Documentation Metrics

- **Total Documentation Files**: 30+
- **Categories**: 5 (Architecture, Guides, Services, Status Reports, Meta)
- **Services Documented**: 2 (Auth, Data)
- **Guide Topics**: 3 (Authentication, Logging, Time Handling)
- **Last Updated**: October 18, 2025

## 🆘 Getting Help

### For Common Issues
1. Check relevant guide in [guides/](guides/)
2. Review [status-reports/](status-reports/) for known issues and fixes
3. Consult service-specific docs in [services/](services/)

### For Architecture Questions
- See [architecture/PRODUCTION_READINESS.md](architecture/PRODUCTION_READINESS.md)
- Review service architecture in [services/](services/)

### For Implementation Examples
- Check [status-reports/](status-reports/) for working examples
- Review service READMEs for code snippets

---

**Platform Version**: 1.0.0  
**Documentation Version**: 2.0 (Restructured)  
**Last Updated**: October 18, 2025

## 📄 Meta Documentation

- [**DOCUMENTATION_ORGANIZATION.md**](DOCUMENTATION_ORGANIZATION.md) - How this documentation was organized (history and structure)
