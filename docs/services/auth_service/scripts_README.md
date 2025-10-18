# Auth Service Scripts

This directory contains utility scripts for the Auth Service.

## Available Scripts

### generate_secure_keys.py

Generates secure random encryption and API keys for production use.

Usage:
```bash
python generate_secure_keys.py
```

This script will:
1. Generate a secure TOKEN_ENCRYPTION_KEY
2. Generate a secure ADMIN_API_KEY
3. Optionally save these to a .env.production file

**Important**: Never commit the generated keys to version control!