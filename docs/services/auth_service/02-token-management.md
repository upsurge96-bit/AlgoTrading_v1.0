# Token Management Guide

## Overview
The token management system handles the complete lifecycle of broker authentication tokens, from creation to expiry.

## Token Lifecycle

### 1. Token Creation
```python
# Example: Creating a new token
token_manager = TokenManager()
token_data = await token_manager.create_token(broker_id="zerodha", request_token="RT123")
```

### 2. Token Storage
- Encrypted at rest using AES-256
- Stored in PostgreSQL
- Cached in Redis
- Backup support

### 3. Token Refresh
The system automatically refreshes tokens before expiry:

```python
# Configuration
TOKEN_EXPIRY_BUFFER = 300  # 5 minutes buffer
MAX_RETRY_ATTEMPTS = 5
BASE_RETRY_DELAY = 2  # seconds
```

#### Refresh Process
1. Calculate refresh time:
   ```python
   refresh_time = token.expiry_time - timedelta(seconds=TOKEN_EXPIRY_BUFFER)
   ```

2. Schedule refresh:
   ```python
   threading.Timer(seconds_until_refresh, refresh_token).start()
   ```

3. Handle failures:
   ```python
   @retry(max_retries=3, backoff_factor=2.0)
   def refresh_token(broker_id: str):
       try:
           new_token = exchange_token(broker_id)
           save_token(new_token)
       except Exception as e:
           handle_refresh_error(e)
   ```

## Error Handling

### Error Classification
```python
def classify_error(error: Exception) -> TokenRefreshError:
    if "unauthorized" in str(error).lower():
        return AuthenticationError(error)
    if "rate limit" in str(error).lower():
        return RateLimitError(error)
    return UnknownError(error)
```

### Retry Strategy
- Exponential backoff
- Jitter for distributed systems
- Circuit breaker pattern

```python
def calculate_retry_delay(attempt: int) -> float:
    delay = BASE_RETRY_DELAY * (2 ** attempt)
    jitter = random.uniform(-JITTER_FACTOR, JITTER_FACTOR) * delay
    return min(delay + jitter, MAX_RETRY_DELAY)
```

## Monitoring & Metrics

### Prometheus Metrics
```python
token_refresh_attempts = Counter(
    "token_refresh_attempts_total",
    "Number of token refresh attempts",
    ["broker", "status"]
)

token_refresh_latency = Histogram(
    "token_refresh_latency_seconds",
    "Token refresh latency",
    ["broker"]
)
```

### Health Checks
```python
def check_token_health(token_data: dict) -> dict:
    return {
        "status": "healthy" if is_token_valid(token_data) else "unhealthy",
        "expires_in": get_expiry_time(token_data),
        "last_refresh": token_data.get("last_refresh"),
        "refresh_attempts": token_data.get("refresh_attempts", 0)
    }
```

## Event Notifications

### Kafka Events
```python
def publish_token_event(event_type: str, token_data: dict):
    # Check if Kafka is enabled
    enable_kafka = os.environ.get("ENABLE_KAFKA", "true").lower() in ("true", "1", "yes", "y")
    if not enable_kafka:
        logger.debug(f"Kafka events disabled, skipping {event_type} event")
        return
        
    event = {
        "type": event_type,
        "broker_id": token_data["broker_id"],
        "timestamp": datetime.utcnow().isoformat(),
        "data": mask_sensitive_data(token_data)
    }
    kafka_producer.send(TOKEN_EVENTS_TOPIC, event)
```

#### Kafka Configuration
The service publishes events to the following topics:
- `auth.token.refresh`: Successful token operations
- `auth.token.error`: Failed token operations

These events enable:
- Real-time monitoring of token health
- Audit trail for security compliance
- Integration with other services (execution, risk, etc.)

You can control Kafka behavior with the following environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `ENABLE_KAFKA` | Enable/disable Kafka events | `true` |
| `KAFKA_BROKERS` | Comma-separated list of brokers | `kafka:9092` |
| `KAFKA_CLIENT` | Client implementation to use (`confluent` or `kafka-python`) | `confluent` |

## CLI Commands

### Token Management
```bash
# Check token status
./token_cli.py status --broker-id zerodha

# Force token refresh
./token_cli.py refresh --broker-id zerodha

# List all tokens
./token_cli.py list

# Get token details
./token_cli.py get --broker-id zerodha
```

## Configuration

### Environment Variables
```env
KITE_API_KEY=your_api_key
KITE_API_SECRET=your_api_secret
TOKEN_ENCRYPTION_KEY=your_encryption_key
REDIS_URL=redis://localhost:6379
KAFKA_BROKERS=localhost:9092
```

### Broker Configuration
```yaml
# broker_config.yaml
brokers:
  - id: zerodha
    name: Zerodha
    type: kite
    settings:
      api_version: 3
      refresh_buffer: 300
      max_retries: 5
```

## Security Considerations

### Token Encryption
```python
def encrypt_token(token: str, key: bytes) -> bytes:
    cipher = AES.new(key, AES.MODE_GCM)
    ciphertext, tag = cipher.encrypt_and_digest(token.encode())
    return b"".join([cipher.nonce, tag, ciphertext])
```

### Access Control
- Admin endpoints protected by API key
- Role-based access control
- Rate limiting per client

## Troubleshooting

### Common Issues
1. Token Refresh Failures
   - Check broker API status
   - Verify API credentials
   - Check network connectivity

2. Storage Issues
   - Verify database connection
   - Check Redis cache status
   - Validate encryption keys

3. Performance Issues
   - Monitor refresh latency
   - Check rate limits
   - Verify resource usage

### Debugging
```python
# Enable debug logging
import logging
logging.getLogger("token_manager").setLevel(logging.DEBUG)
```

## Best Practices

1. **Token Security**
   - Never log full tokens
   - Rotate encryption keys
   - Use secure storage

2. **Error Handling**
   - Implement circuit breakers
   - Use exponential backoff
   - Monitor error rates

3. **Monitoring**
   - Set up alerts
   - Track metrics
   - Log key events