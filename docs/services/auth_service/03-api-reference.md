# API Documentation

## Authentication Endpoints

### 1. Token Generation

```http
POST /auth/token
```

Generate a new authentication token for a broker.

#### Request Body
```json
{
    "broker_id": "zerodha",
    "request_token": "RT123456",
    "api_key": "YOUR_API_KEY"
}
```

#### Response
```json
{
    "access_token": "eyJhbGciOiJ...",
    "expires_in": 3600,
    "token_type": "bearer"
}
```

#### Error Responses
```json
{
    "error": "invalid_request",
    "error_description": "Invalid request token"
}
```

### 2. Token Refresh

```http
POST /auth/refresh
```

Refresh an existing authentication token.

#### Request Headers
```
Authorization: Bearer <access_token>
```

#### Response
```json
{
    "access_token": "eyJhbGciOiJ...",
    "expires_in": 3600,
    "token_type": "bearer"
}
```

### 3. Token Validation

```http
GET /auth/validate
```

Validate an existing token.

#### Request Headers
```
Authorization: Bearer <access_token>
```

#### Response
```json
{
    "valid": true,
    "expires_in": 2400,
    "broker_id": "zerodha"
}
```

### 4. Token Revocation

```http
POST /auth/revoke
```

Revoke an existing token.

#### Request Headers
```
Authorization: Bearer <access_token>
```

#### Response
```json
{
    "message": "Token revoked successfully"
}
```

## Admin Endpoints

### 1. List Active Tokens

```http
GET /admin/tokens
```

List all active tokens.

#### Request Headers
```
X-API-Key: <admin_api_key>
```

#### Response
```json
{
    "tokens": [
        {
            "broker_id": "zerodha",
            "expires_at": "2024-01-20T15:30:00Z",
            "last_refresh": "2024-01-20T12:30:00Z"
        }
    ]
}
```

### 2. Force Token Refresh

```http
POST /admin/tokens/{broker_id}/refresh
```

Force refresh a token for a specific broker.

#### Request Headers
```
X-API-Key: <admin_api_key>
```

#### Response
```json
{
    "message": "Token refresh initiated",
    "status": "success"
}
```

### 3. Health Check

```http
GET /health
```

Check service health status.

#### Response
```json
{
    "status": "healthy",
    "components": {
        "database": "up",
        "redis": "up",
        "kafka": "up"
    }
}
```

## WebSocket Events

### 1. Token Events Stream

```websocket
GET /ws/token-events
```

Stream token-related events.

#### Connection Parameters
```
?api_key=<api_key>
```

#### Event Types

1. Token Created
```json
{
    "type": "token.created",
    "broker_id": "zerodha",
    "timestamp": "2024-01-20T12:00:00Z"
}
```

2. Token Refreshed
```json
{
    "type": "token.refreshed",
    "broker_id": "zerodha",
    "timestamp": "2024-01-20T12:30:00Z"
}
```

3. Token Expired
```json
{
    "type": "token.expired",
    "broker_id": "zerodha",
    "timestamp": "2024-01-20T15:30:00Z"
}
```

## Rate Limits

| Endpoint | Rate Limit | Window |
|----------|------------|--------|
| /auth/token | 5 | 1 minute |
| /auth/refresh | 10 | 1 minute |
| /auth/validate | 100 | 1 minute |
| /admin/* | 100 | 1 minute |

## Response Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 400 | Bad Request |
| 401 | Unauthorized |
| 403 | Forbidden |
| 429 | Too Many Requests |
| 500 | Internal Server Error |

## Error Codes

| Code | Description |
|------|-------------|
| invalid_request | The request is missing a required parameter |
| invalid_token | The access token is invalid |
| expired_token | The access token has expired |
| insufficient_scope | The request requires higher privileges |
| server_error | Internal server error |

## Request Examples

### cURL

1. Generate Token
```bash
curl -X POST https://api.example.com/auth/token \
  -H "Content-Type: application/json" \
  -d '{
    "broker_id": "zerodha",
    "request_token": "RT123456",
    "api_key": "YOUR_API_KEY"
  }'
```

2. Refresh Token
```bash
curl -X POST https://api.example.com/auth/refresh \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Python

```python
import requests

def generate_token(broker_id: str, request_token: str, api_key: str):
    response = requests.post(
        "https://api.example.com/auth/token",
        json={
            "broker_id": broker_id,
            "request_token": request_token,
            "api_key": api_key
        }
    )
    return response.json()

def refresh_token(access_token: str):
    response = requests.post(
        "https://api.example.com/auth/refresh",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    return response.json()
```