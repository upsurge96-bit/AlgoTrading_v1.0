# Auth Service Restructuring Plan

## Current Issues
- Utility files are scattered (retry_utils.py, token_security.py, idempotency.py)
- API routes are not organized by functionality
- Middleware and configuration files are at the top level
- Documentation and README need better organization

## Proposed Structure

```
services/auth_service/
│
├── api/                       # API routes and controllers
│   ├── __init__.py            # API initialization
│   ├── routes/                # Route handlers by feature
│   │   ├── __init__.py        # Route registration
│   │   ├── auth_routes.py     # Authentication routes
│   │   ├── token_routes.py    # Token management routes
│   │   ├── admin_routes.py    # Admin-only routes
│   │   └── health_routes.py   # Health check routes
│   └── middlewares/           # API middlewares
│       ├── __init__.py        # Middleware registration
│       ├── auth_middleware.py # Authentication middleware
│       ├── rate_limit.py      # Rate limiting
│       └── logging.py         # Request logging
│
├── core/                      # Core business logic
│   ├── __init__.py            # Core initialization
│   ├── auth/                  # Auth domain
│   │   ├── __init__.py        
│   │   └── token_manager.py   # Token management logic
│   └── services/              # Application services
│       ├── __init__.py
│       ├── token_service.py   # Token related services
│       └── status_service.py  # Status reporting
│
├── data/                      # Data storage
│   ├── __init__.py
│   ├── models/                # Domain models
│   │   ├── __init__.py
│   │   └── token_model.py     # Token model
│   └── repositories/          # Data access
│       ├── __init__.py
│       └── token_repository.py # Token data access
│
├── utils/                     # Utility functions
│   ├── __init__.py
│   ├── security/
│   │   ├── __init__.py
│   │   ├── encryption.py      # Token encryption
│   │   └── token_security.py  # Token security functions
│   ├── retry.py               # Retry logic
│   ├── idempotency.py         # Idempotency helpers
│   └── config.py              # Configuration utilities
│
├── static/                    # Static assets for UI
│
├── templates/                 # UI templates
│
├── tests/                     # Tests
│   ├── __init__.py
│   ├── unit/                  # Unit tests
│   └── integration/           # Integration tests
│
├── config/                    # Configuration files
│   ├── __init__.py
│   └── logging_config.py      # Logging configuration
│
├── docs/                      # Documentation
│
├── main.py                    # Application entry point
├── db_setup.py                # Database setup script
├── Dockerfile                 # Docker configuration
├── requirements.txt           # Dependencies
├── .env.example               # Environment variables example
└── README.md                  # Project documentation
```

## Implementation Steps

1. Create the new directory structure
2. Move files to their appropriate locations
3. Update imports as needed
4. Ensure tests pass after restructuring
5. Update documentation to reflect new structure

## Benefits

- Better organization of code by domain and function
- Clearer separation of concerns
- More maintainable and scalable codebase
- Easier for new developers to understand the project structure
- Better adherence to clean architecture principles