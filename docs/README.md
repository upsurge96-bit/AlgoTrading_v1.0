# AlgoTrading Platform Documentation

Welcome to the comprehensive documentation for the AlgoTrading platform. This documentation is organized into logical sections for easy navigation.

## 📁 Documentation Structure

```
docs/
├── README.md                       # This file
├── architecture/                   # System Architecture & Design
│   ├── PRODUCTION_READINESS.md    # Production deployment guide
│   ├── MULTI_GRANULARITY_IMPLEMENTATION.md # Data pipeline design
│   └── STRUCTURE.md               # Project structure
├── guides/                         # How-to Guides & Best Practices
│   ├── CORE_UTILITIES.md         # Core utilities guide
│   ├── authentication/            # Auth & Security guides
│   ├── logging/                   # Logging system guides
│   └── time-handling/             # Time & timezone guides
├── services/                       # Service-Specific Documentation
│   ├── auth_service/              # Auth service docs
│   └── data_service/              # Data service docs
│       └── monitoring/            # Monitoring guides (NEW!)
├── operations/                     # Operations & Troubleshooting (NEW!)
│   ├── testing/                   # Test procedures & reports
│   └── troubleshooting/           # Diagnostic guides
├── development/                    # Development Documentation (NEW!)
│   ├── refactoring/               # Refactoring history
│   └── quick-reference/           # Quick reference guides
└── reports/                        # Status Reports & Summaries (NEW!)
    ├── final/                     # Final verification reports
    ├── status/                    # Status reports
    └── archive/                   # Historical documentation
```

## 📖 Documentation Sections

### 🏗️ [Architecture](./architecture/)
System design, architecture patterns, and production deployment guides.
- [Production Readiness](./architecture/PRODUCTION_READINESS.md) - Deployment guide
- [Multi-Granularity Pipeline](./architecture/MULTI_GRANULARITY_IMPLEMENTATION.md) - Data pipeline
- [Project Structure](./architecture/STRUCTURE.md) - Codebase organization

### � [Guides](./guides/)
Development guides, best practices, and how-to documentation.

#### Core Utilities
- [Core Utilities Guide](./guides/CORE_UTILITIES.md) - **START HERE** for logging & config

#### Authentication & Security
- [Best Practices](./guides/authentication/auth_best_practices.md) - Security standards
- [Setup Guide](./guides/authentication/READY_FOR_LOGIN.md) - OAuth configuration

#### Logging System
- [Logging Guide](./guides/logging/logging_guide.md) - How to use logging
- [Standards](./guides/logging/logging_standardization.md) - Logging conventions

#### Time Handling
- [Time Handling](./guides/time-handling/time_handling.md) - Timezone management
- [Time Q&A](./guides/time-handling/time_handling_interview.md) - In-depth guide

### 🔧 [Services](./services/)
Service-specific documentation with API references and setup guides.
- [Auth Service](./services/auth_service/) - OAuth 2.0, token management
- [Data Service](./services/data_service/) - Market data streaming
  - [Monitoring](./services/data_service/monitoring/) - Heartbeat & market status

### ⚙️ [Operations](./operations/)
Operational guides, testing, and troubleshooting documentation.
- [Testing](./operations/testing/) - Verification reports and test procedures
- [Troubleshooting](./operations/troubleshooting/) - Diagnostic guides and status reports

### 💻 [Development](./development/)
Development documentation, refactoring history, and quick references.
- [Refactoring History](./development/refactoring/) - Code reorganization docs
- [Quick Reference](./development/quick-reference/) - Command cheat sheets

### 📊 [Reports](./reports/)
System status reports, verification results, and implementation summaries.
- [Final Reports](./reports/final/) - Comprehensive verification reports
- [Status Reports](./reports/status/) - Current and historical status
- [Archive](./reports/archive/) - Historical documentation

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
- 📘 [Production Deployment](./architecture/PRODUCTION_READINESS.md)
- ⚙️ [Core Utilities Guide](./guides/CORE_UTILITIES.md) - **START HERE**
- 🔐 [Authentication Setup](./guides/authentication/READY_FOR_LOGIN.md)
- 📊 [Logging Best Practices](./guides/logging/logging_guide.md)
- ⏰ [Time Handling Guide](./guides/time-handling/time_handling.md)
- 💓 [Heartbeat Monitoring](./services/data_service/monitoring/HEARTBEAT_MONITORING.md)
- 🌐 [Market Status Logging](./services/data_service/monitoring/MARKET_STATUS_LOGGING.md)
- 🔧 [Troubleshooting Guide](./operations/troubleshooting/)
- 🎯 [Final Verification Report](./reports/final/FINAL_VERIFICATION_REPORT.md)
- ⚡ [Quick Reference](./development/quick-reference/)

## 📝 Contributing to Documentation

### Adding New Documentation

1. **Choose the right location**:
   - Architecture docs → `architecture/`
   - How-to guides → `guides/<topic>/`
   - Service docs → `services/<service_name>/`
   - Test reports → `operations/testing/`
   - Troubleshooting → `operations/troubleshooting/`
   - Refactoring docs → `development/refactoring/`
   - Status reports → `reports/status/`
   - Final reports → `reports/final/`

2. **Follow naming conventions**:
   - Use descriptive names: `SERVICE_STATUS.md` not `status.md`
   - Use uppercase for important: `README.md`, `SETUP_GUIDE.md`
   - Use lowercase for detailed: `01-architecture.md`
   - Use hyphens for multi-word: `auth-best-practices.md`

3. **Update indexes**:
   - Add links to this README
   - Update relevant section READMEs
   - Update parent directory README

### Documentation Standards

- ✅ Use clear, descriptive headings
- ✅ Include code examples where applicable
- ✅ Add diagrams for complex concepts
- ✅ Keep documentation in sync with code
- ✅ Use emoji icons for visual navigation
- ✅ Link to related documentation
- ✅ Include troubleshooting sections
- ✅ Add quick reference tables

## �️ Development Stack

- **Python**: 3.12+
- **Framework**: FastAPI
- **Database**: PostgreSQL 14 + TimescaleDB
- **Message Queue**: Apache Kafka
- **Object Storage**: MinIO
- **Monitoring**: Prometheus + Grafana
- **Container**: Docker + Docker Compose

## 📊 Documentation Metrics

- **Total Documentation Files**: 60+
- **Main Categories**: 7 (Architecture, Guides, Services, Operations, Development, Reports, Meta)
- **Services Documented**: 2 (Auth, Data)
- **Guide Topics**: 3 (Authentication, Logging, Time Handling)
- **Status Reports**: 10+
- **Last Reorganization**: October 19, 2025

## 🆘 Getting Help

### For Common Issues
1. Check [operations/troubleshooting/](./operations/troubleshooting/) for diagnostic guides
2. Review [development/quick-reference/](./development/quick-reference/) for common commands
3. Consult service-specific docs in [services/](./services/)

### For Testing & Verification
1. See [operations/testing/](./operations/testing/) for test procedures
2. Review [reports/final/](./reports/final/) for verification results
3. Check [reports/status/](./reports/status/) for current system status

### For Architecture Questions
- See [architecture/PRODUCTION_READINESS.md](./architecture/PRODUCTION_READINESS.md)
- Review [architecture/MULTI_GRANULARITY_IMPLEMENTATION.md](./architecture/MULTI_GRANULARITY_IMPLEMENTATION.md)
- Check service architecture in [services/](./services/)

### For Development Help
- Review [development/refactoring/](./development/refactoring/) for code organization
- Check [guides/CORE_UTILITIES.md](./guides/CORE_UTILITIES.md) for utility usage
- See [development/quick-reference/](./development/quick-reference/) for commands

---

**Platform Version**: 1.0.0  
**Documentation Version**: 3.0 (Fully Restructured)  
**Last Updated**: October 19, 2025

## 📄 Meta Documentation

- [**DOCS_REORGANIZATION_PLAN.md**](../DOCS_REORGANIZATION_PLAN.md) - Reorganization plan (in root)
- [**Documentation Archive**](./reports/archive/) - Historical documentation
