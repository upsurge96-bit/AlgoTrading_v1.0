@echo off
echo ==============================================================================
echo 5-YEAR DATA GENERATION - PROGRESS MONITOR
echo ==============================================================================
echo.
echo Clearing database...
docker exec timescaledb psql -U trader -d trading -c "DELETE FROM ohlcv_data;" >nul 2>&1
timeout /t 2 /nobreak >nul 2>&1
echo Database cleared!
echo.
echo Starting generation in background...
start /B docker exec data_service python /app/generate_5year_data.py >generation_output.log 2>&1
echo.
echo Monitoring progress (will update every 10 seconds)...
echo Press Ctrl+C to stop monitoring (generation will continue)
echo ==============================================================================
echo.

:LOOP
timeout /t 10 /nobreak >nul 2>&1
cls
echo ==============================================================================
echo 5-YEAR DATA GENERATION - PROGRESS MONITOR
echo ==============================================================================
echo Current Time: %TIME%
echo ==============================================================================
echo.
echo DATABASE RECORD COUNTS:
echo ------------------------------------------------------------------------------
docker exec timescaledb psql -U trader -d trading -c "SELECT interval, COUNT(*) as records, COUNT(DISTINCT instrument_token) as instruments, MIN(timestamp)::date as first_date, MAX(timestamp)::date as last_date FROM ohlcv_data GROUP BY interval ORDER BY CASE interval WHEN '1m' THEN 1 WHEN '5m' THEN 2 WHEN '15m' THEN 3 WHEN '1h' THEN 4 WHEN '1d' THEN 5 END;"
echo.
echo ==============================================================================
echo Next update in 10 seconds... (Press Ctrl+C to exit)
echo ==============================================================================
goto LOOP
