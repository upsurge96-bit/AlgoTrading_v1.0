# Authentication & Security Guides

Documentation for OAuth 2.0 integration, authentication flows, and security best practices.

## 📋 Contents

- [**auth_best_practices.md**](auth_best_practices.md) - Security best practices for authentication
- [**auth_service_cleanup.md**](auth_service_cleanup.md) - Auth service cleanup and refactoring notes
- [**auth_service_learnings.md**](auth_service_learnings.md) - Lessons learned from implementation
- [**READY_FOR_LOGIN.md**](READY_FOR_LOGIN.md) - OAuth setup and login readiness guide

## 🔐 OAuth 2.0 Flow

The platform uses OAuth 2.0 with Zerodha Kite Connect API:

```
┌──────────┐         ┌──────────┐         ┌──────────┐
│  Client  │────────▶│   Auth   │────────▶│  Kite    │
│  (User)  │         │ Service  │         │   API    │
└──────────┘         └──────────┘         └──────────┘
     │                     │                     │
     │ 1. Login Request    │                     │
     │────────────────────▶│                     │
     │                     │                     │
     │ 2. Redirect to Kite │                     │
     │◀────────────────────│                     │
     │                     │                     │
     │ 3. Authenticate     │                     │
     │─────────────────────────────────────────▶│
     │                     │                     │
     │ 4. Auth Code        │                     │
     │◀─────────────────────────────────────────│
     │                     │                     │
     │ 5. Exchange Code    │                     │
     │────────────────────▶│                     │
     │                     │ 6. Get Access Token │
     │                     │────────────────────▶│
     │                     │                     │
     │                     │ 7. Access Token     │
     │                     │◀────────────────────│
     │                     │                     │
     │ 8. Session Token    │                     │
     │◀────────────────────│                     │
```

## 🎯 Quick Start

1. **Setup OAuth Credentials**
   ```bash
   # In config/secrets.env
   KITE_API_KEY=your_api_key
   KITE_API_SECRET=your_api_secret
   KITE_REDIRECT_URL=http://localhost:8018/callback
   ```

2. **Start Auth Service**
   ```bash
   docker-compose up -d auth_service
   ```

3. **Initiate Login**
   - Visit: http://localhost:8018/login
   - Login with Kite credentials
   - Authorize the application

4. **Verify Token**
   - Check: http://localhost:8018/token
   - Access token should be available

For detailed setup, see [READY_FOR_LOGIN.md](READY_FOR_LOGIN.md)

## 🛡️ Security Best Practices

### Token Management
- ✅ Tokens encrypted with AES-256
- ✅ Tokens cached with TTL (6 hours)
- ✅ Auto-refresh before expiry
- ✅ Secure session cookies

### Database Security
- ✅ Credentials encrypted at rest
- ✅ Separate database user per service
- ✅ Connection pooling with limits
- ✅ Prepared statements (no SQL injection)

### API Security
- ✅ HTTPS in production
- ✅ Rate limiting
- ✅ Request validation
- ✅ CORS configuration

For complete best practices, see [auth_best_practices.md](auth_best_practices.md)

## 🔧 Implementation Details

### Token Lifecycle
1. **Request Token** - User clicks login
2. **Authorization** - User authorizes on Kite
3. **Exchange** - Request token → Access token
4. **Storage** - Encrypted and cached
5. **Refresh** - Auto-refresh before expiry
6. **Cleanup** - Expired tokens removed

### Session Management
- Sessions stored in PostgreSQL
- Redis caching for fast access
- Session TTL: 24 hours
- Automatic cleanup of expired sessions

## 📚 Related Documentation

- [Auth Service Architecture](../../services/auth_service/01-architecture.md)
- [Token Management](../../services/auth_service/02-token-management.md)
- [API Reference](../../services/auth_service/03-api-reference.md)
- [Auth Service Setup](../../services/auth_service/SETUP_GUIDE.md)

## 🐛 Common Issues

### Issue: "Token is invalid or has expired"
**Solution**: Check [CRITICAL_FIX_APPLIED.md](../../status-reports/CRITICAL_FIX_APPLIED.md)

### Issue: OAuth redirect fails
**Solution**: Verify `KITE_REDIRECT_URL` matches Kite Connect app settings

### Issue: Token not persisting
**Solution**: Check database connection and encryption key configuration

---

**Last Updated**: October 18, 2025
