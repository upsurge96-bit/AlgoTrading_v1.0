# Development Guide

## Setup Development Environment

### 1. Prerequisites

- Python 3.12+
- PostgreSQL 15+
- Redis 7+
- Kafka 3.5+

### 2. Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd auth-service
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
.\venv\Scripts\activate   # Windows
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
cp config/secrets.env.example config/secrets.env
# Edit secrets.env with your credentials
```

### 3. Database Setup

1. Create database:
```sql
CREATE DATABASE auth_service;
```

2. Run migrations:
```bash
alembic upgrade head
```

## Development Workflow

### 1. Code Structure

```
auth_service/
├── api/
│   ├── __init__.py
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── admin.py
│   │   └── auth.py
│   └── dependencies.py
├── core/
│   ├── __init__.py
│   ├── config.py
│   └── security.py
├── db/
│   ├── __init__.py
│   ├── models.py
│   └── session.py
├── services/
│   ├── __init__.py
│   └── token_service.py
├── schemas/
│   ├── __init__.py
│   └── token.py
└── main.py
```

### 2. Adding New Features

1. Create feature branch:
```bash
git checkout -b feature/new-feature
```

2. Follow development steps:
   - Add new models in `db/models.py`
   - Create migrations using Alembic
   - Add routes in `api/routes/`
   - Update services in `services/`
   - Add tests

3. Run tests:
```bash
pytest tests/
```

### 3. Code Style

We follow PEP 8 guidelines. Use pre-commit hooks:

```bash
pre-commit install
```

### 4. Testing

#### Unit Tests

```python
# test_token_service.py
from auth_service.services import TokenService

def test_token_creation():
    service = TokenService()
    token = service.create_token(broker_id="test")
    assert token is not None
    assert token.broker_id == "test"
```

#### Integration Tests

```python
# test_auth_api.py
from fastapi.testclient import TestClient
from auth_service.main import app

client = TestClient(app)

def test_token_endpoint():
    response = client.post(
        "/auth/token",
        json={
            "broker_id": "test",
            "request_token": "RT123"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
```

## Docker Development

### Local Development with Docker

1. Build image:
```bash
docker build -t auth-service:dev .
```

2. Run container:
```bash
docker run -p 8000:8000 \
  --env-file config/secrets.env \
  auth-service:dev
```

### Docker Compose Setup

```yaml
version: '3.8'
services:
  auth-service:
    build: .
    ports:
      - "8000:8000"
    env_file:
      - config/secrets.env
    depends_on:
      - postgres
      - redis
      - kafka

  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: auth_service
      POSTGRES_USER: user
      POSTGRES_PASSWORD: password

  redis:
    image: redis:7

  kafka:
    image: confluentinc/cp-kafka:7.0.0
```

## Monitoring & Debugging

### 1. Logging

```python
import logging

logger = logging.getLogger(__name__)

logger.info("Token created", extra={
    "broker_id": broker_id,
    "expires_in": token.expires_in
})
```

### 2. Metrics

```python
from prometheus_client import Counter, Histogram

token_creation_total = Counter(
    "token_creation_total",
    "Total number of tokens created",
    ["broker"]
)

token_refresh_duration = Histogram(
    "token_refresh_duration_seconds",
    "Time spent refreshing tokens",
    ["broker"]
)
```

### 3. Debugging

Enable debug mode in `config.yaml`:

```yaml
debug:
  enabled: true
  log_level: DEBUG
  show_sql: true
```

## Deployment

### 1. Production Configuration

```yaml
# config/production.yaml
server:
  host: 0.0.0.0
  port: 8000
  workers: 4

database:
  pool_size: 20
  max_overflow: 10
  pool_timeout: 30

redis:
  pool_size: 10
  socket_timeout: 5

security:
  token_expiry: 3600
  refresh_buffer: 300
```

### 2. Health Checks

Implement in your deployment:

```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /health/ready
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 5
```

### 3. Resource Requirements

```yaml
resources:
  requests:
    cpu: 500m
    memory: 512Mi
  limits:
    cpu: 1000m
    memory: 1Gi
```

## Troubleshooting

### 1. Common Issues

1. Database Connection Issues
```python
def check_db_connection():
    try:
        db.session.execute("SELECT 1")
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False
```

2. Token Refresh Failures
```python
def diagnose_refresh_failure(error):
    if isinstance(error, TokenExpiredError):
        logger.error("Token expired before refresh")
    elif isinstance(error, NetworkError):
        logger.error("Network connectivity issues")
    else:
        logger.error(f"Unknown error: {error}")
```

### 2. Performance Issues

1. Connection Pooling
```python
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=20,
    max_overflow=10,
    pool_timeout=30
)
```

2. Caching
```python
from functools import lru_cache

@lru_cache(maxsize=1000, ttl=300)
def get_token_info(token_id: str) -> dict:
    return token_service.get_token(token_id)
```

## Security

### 1. Token Encryption

```python
from cryptography.fernet import Fernet

def encrypt_token(token: str) -> str:
    f = Fernet(ENCRYPTION_KEY)
    return f.encrypt(token.encode()).decode()

def decrypt_token(encrypted_token: str) -> str:
    f = Fernet(ENCRYPTION_KEY)
    return f.decrypt(encrypted_token.encode()).decode()
```

### 2. API Security

1. Rate Limiting
```python
from fastapi import Depends
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/auth/token")
@limiter.limit("5/minute")
async def create_token(request):
    pass
```

2. Input Validation
```python
from pydantic import BaseModel, validator

class TokenRequest(BaseModel):
    broker_id: str
    request_token: str

    @validator("broker_id")
    def validate_broker_id(cls, v):
        if not is_valid_broker_id(v):
            raise ValueError("Invalid broker ID")
        return v
```