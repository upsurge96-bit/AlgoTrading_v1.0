@echo off
REM ============================================================================
REM Heartbeat Monitor - Real-time data flow monitoring
REM ============================================================================

echo.
echo ========================================================================
echo   HEARTBEAT MONITOR - Press Ctrl+C to stop
echo ========================================================================
echo.
echo Monitoring: Live data processor heartbeat, errors, and warnings
echo Log file: logs\data_service.log
echo.
echo ========================================================================
echo.

REM Monitor docker logs for heartbeat, errors, and warnings
docker logs -f data_service 2>&1 | findstr /C:"HEARTBEAT" /C:"ERROR" /C:"WARNING" /C:"✅" /C:"❌" /C:"⚠️"
