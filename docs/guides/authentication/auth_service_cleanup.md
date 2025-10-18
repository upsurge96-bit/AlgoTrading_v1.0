# Unused Files in Auth Service

After reviewing the codebase, the following files have been identified as unused, redundant, or duplicated. They can be safely removed:

## Duplicate Files

1. **token_security.py** in the root directory:
   - This is a duplicate of `utils/security/token_security.py`
   - The code is nearly identical, but the utility version uses the core logger
   - Only `utils/security/token_security.py` is being imported (via `utils.security`)

2. **retry_utils.py**:
   - This is a duplicate of `utils/retry.py`
   - The files are identical
   - Code is importing from `core.utils.retry` instead

3. **idempotency.py**:
   - This is a duplicate of `utils/idempotency.py`
   - The files are identical
   - Imports are using the version in `utils.idempotency`

## Unnecessary Files

4. **app.py**:
   - This was created as a temporary fix to expose the app from api.py
   - It's now unused since we're using `main_api.py` directly in the Dockerfile

## Recommendations

Delete these files to clean up the codebase and reduce confusion:

```
services/auth_service/token_security.py
services/auth_service/retry_utils.py
services/auth_service/idempotency.py
services/auth_service/app.py
```

This will help maintain a cleaner codebase and avoid confusion about which implementation should be used.