@echo off
REM ============================================================================
REM AlgoTrading Platform - Quick Verification Script
REM ============================================================================

echo.
echo ========================================================================
echo   ALGOTRADING PLATFORM - SYSTEM VERIFICATION
echo ========================================================================
echo.

REM Check Docker is running
echo [1/10] Checking Docker...
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo    ❌ Docker not running or not installed
    goto :end
) else (
    echo    ✅ Docker is running
)

REM Check services
echo.
echo [2/10] Checking Docker services...
docker-compose ps | findstr "Up"
if %errorlevel% neq 0 (
    echo    ⚠️  Some services may not be running
) else (
    echo    ✅ Services are running
)

REM Check data_service health
echo.
echo [3/10] Checking data_service health...
curl -s http://localhost:8080/api/v1/health >nul 2>&1
if %errorlevel% neq 0 (
    echo    ⚠️  Data service not responding
) else (
    echo    ✅ Data service responding
)

REM Check auth_service health
echo.
echo [4/10] Checking auth_service health...
curl -s http://localhost:8018/health >nul 2>&1
if %errorlevel% neq 0 (
    echo    ⚠️  Auth service not responding
) else (
    echo    ✅ Auth service responding
)

REM Check database
echo.
echo [5/10] Checking TimescaleDB...
docker exec timescaledb pg_isready -U trader >nul 2>&1
if %errorlevel% neq 0 (
    echo    ❌ Database not ready
) else (
    echo    ✅ Database ready
)

REM Check MinIO
echo.
echo [6/10] Checking MinIO...
docker exec minio mc ls minio/market-data >nul 2>&1
if %errorlevel% neq 0 (
    echo    ⚠️  MinIO bucket not accessible
) else (
    echo    ✅ MinIO accessible
)

REM Check load directory in container
echo.
echo [7/10] Checking load modules in container...
docker exec data_service ls /app/services/data_service/load/historical_data.py >nul 2>&1
if %errorlevel% neq 0 (
    echo    ❌ Load modules NOT found in container
    echo    ⚠️  REBUILD REQUIRED: docker-compose build data_service
) else (
    echo    ✅ Load modules found
)

REM Check load directory on host
echo.
echo [8/10] Checking load modules on host...
if exist "services\data_service\load\historical_data.py" (
    echo    ✅ historical_data.py exists
) else (
    echo    ❌ historical_data.py missing
)
if exist "services\data_service\load\live_data.py" (
    echo    ✅ live_data.py exists
) else (
    echo    ❌ live_data.py missing
)

REM Check documentation
echo.
echo [9/10] Checking documentation...
if exist ".github\copilot-instructions.md" (
    echo    ✅ AI instructions exist
) else (
    echo    ❌ AI instructions missing
)
if exist "services\data_service\load\README.md" (
    echo    ✅ Load module documentation exists
) else (
    echo    ❌ Load module documentation missing
)

REM Count database tables
echo.
echo [10/10] Checking database tables...
docker exec timescaledb psql -U trader -d trading -t -c "SELECT COUNT(*) FROM pg_tables WHERE schemaname = 'public';" 2>nul
if %errorlevel% neq 0 (
    echo    ⚠️  Cannot query database
) else (
    echo    ✅ Database tables accessible
)

echo.
echo ========================================================================
echo   VERIFICATION COMPLETE
echo ========================================================================
echo.

REM Final summary
echo SUMMARY:
echo   - See PROJECT_VERIFICATION.md for detailed report
echo   - If load modules missing in container, rebuild:
echo     docker-compose build data_service
echo     docker-compose up -d data_service
echo.

:end
pause
