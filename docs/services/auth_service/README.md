# Secure Token Generator Service

This service provides secure generation and storage of Kite Connect API access tokens.

## Security Features

- **Encrypted Token Storage**: All tokens are encrypted at rest using Fernet symmetric encryption
- **Secure File Permissions**: File permissions are set to prevent unauthorized access
- **API Key Authentication**: Admin endpoints require API key authentication
- **Data Directory Isolation**: Tokens stored in a dedicated data directory with restricted access
- **Automatic Token Validation**: Periodic checks for token validity

## Setup Instructions

### 1. Configure Environment Variables

Copy the example environment file and update it with your actual values:

```bash
cp .env.example .env
```

Edit `.env` and set your Kite API credentials:

```
KITE_API_KEY=your_kite_api_key
KITE_API_SECRET=your_api_secret
```

### 2. Generate Secure Keys for Production

Run the provided script to generate secure random keys:

```bash
python scripts/generate_secure_keys.py
```

This will generate:
- A secure TOKEN_ENCRYPTION_KEY for encrypting tokens
- An ADMIN_API_KEY for accessing admin endpoints

### 3. Update Production Config

For production, add these secure keys to `config/secrets.env`:

```
TOKEN_ENCRYPTION_KEY=your_generated_key
ADMIN_API_KEY=your_generated_admin_key
```

**IMPORTANT:** Never commit these keys to version control!

## Usage

### Accessing Token Data

To access the token data programmatically, use the admin API with your API key:

```bash
curl -H "X-Admin-API-Key: your_admin_key" http://localhost:8018/admin/token
```

### Retrieving Token Status

Check token status without authentication:

```bash
curl http://localhost:8018/status
```

### Manual Token Generation

1. Access the web interface at http://localhost:8018
2. Click "Login to Kite" and complete the Zerodha login process
3. You will be redirected back to the service when complete

## Security Best Practices

1. Change the default ADMIN_API_KEY in production
2. Use a strong TOKEN_ENCRYPTION_KEY
3. Run the service behind a reverse proxy with TLS
4. Limit network access to the service
5. Rotate encryption keys periodically (requires re-encrypting tokens)
6. Monitor logs for unauthorized access attempts