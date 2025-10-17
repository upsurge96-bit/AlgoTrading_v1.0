"""
Monitoring Service — Algo Trading Platform (clean)
-----------------------------------------------
Exposes:
  - /health    : cached health of monitored services
  - /healthz   : alias for /health (back-compat)
  - /metrics   : Prometheus metrics

This module keeps config loading and logging centralized.
"""

import os
import time
import asyncio
import httpx
from datetime import datetime

from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST

from core.utils.logger import get_logger
from core.utils.config_loader import load_config

# -------------------------------------------------
# Initialization
# -------------------------------------------------
logger = get_logger("monitoring_service")

try:
    CONFIG = load_config("/app/config/config.yaml")
    logger.info("✅ Loaded config from: /app/config/config.yaml")
except Exception as e:
    logger.warning(f"⚠️ Could not load config.yaml: {e}")
    CONFIG = {}

# Default monitored services
DEFAULT_SERVICES = {
    "data_service": os.getenv("DATA_URL", "http://data_service:8080/health"),
    "auth_service": os.getenv("AUTH_URL", "http://auth_service:8018/health"),
}
SERVICES = CONFIG.get("monitoring", {}).get("targets", DEFAULT_SERVICES)
logger.info(f"🩺 Monitoring targets: {list(SERVICES.keys())}")

# -------------------------------------------------
# FastAPI App
# -------------------------------------------------
app = FastAPI(title="Monitoring Service", version="2.0")

# -------------------------------------------------
# Prometheus Metrics
# -------------------------------------------------
service_health = Gauge("service_health_status", "Health status of monitored services", ["service"])
health_checks_total = Counter("health_checks_total", "Total health checks performed", ["service"])
health_check_failures = Counter("health_check_failures_total", "Total health check failures", ["service"])
service_latency = Histogram("service_response_time_seconds", "Response latency for monitored services", ["service"])

# -------------------------------------------------
# Cached Health Data
# -------------------------------------------------
last_health_status = {"status": "unknown", "updated_at": None, "services": {}}
CHECK_INTERVAL = int(os.getenv("HEALTH_CHECK_INTERVAL", "30"))


async def perform_health_checks():
    """Check monitored services and update Prometheus metrics."""
    results = {}
    async with httpx.AsyncClient(timeout=3) as client:
        for name, url in SERVICES.items():
            start_time = time.perf_counter()
            try:
                resp = await client.get(url)
                duration = time.perf_counter() - start_time
                service_latency.labels(service=name).observe(duration)
                health_checks_total.labels(service=name).inc()

                if resp.status_code == 200:
                    results[name] = {"status": "up", "latency": round(duration, 3)}
                    service_health.labels(service=name).set(1)
                    logger.info(f"✅ {name} is UP ({url}) [{duration:.3f}s]")
                else:
                    results[name] = {"status": f"down ({resp.status_code})"}
                    service_health.labels(service=name).set(0)
                    health_check_failures.labels(service=name).inc()
                    logger.warning(f"⚠️ {name} DOWN ({resp.status_code})")
            except Exception as e:
                results[name] = {"status": "error", "message": str(e)}
                service_health.labels(service=name).set(0)
                health_check_failures.labels(service=name).inc()
                logger.error(f"❌ {name} unreachable ({url}) → {e}")

    overall_status = "healthy" if all(v.get("status") == "up" for v in results.values()) else "degraded"
    return {
        "status": overall_status,
        "updated_at": datetime.utcnow().isoformat(),
        "services": results,
    }


@app.on_event("startup")
async def startup_event():
    """Start background scheduler for health checks and store task on app.state."""
    global last_health_status

    async def scheduler():
        global last_health_status
        while True:
            try:
                last_health_status = await perform_health_checks()
            except Exception as e:
                logger.exception("Error during health checks: %s", e)
            await asyncio.sleep(CHECK_INTERVAL)

    # Store the scheduler task so we can cancel on shutdown
    app.state.health_task = asyncio.create_task(scheduler())
    logger.info("🕒 Background health monitor started (interval=%ss)", CHECK_INTERVAL)


@app.on_event("shutdown")
async def shutdown_event():
    """Cancel background scheduler on shutdown."""
    health_task = getattr(app.state, "health_task", None)
    if health_task:
        health_task.cancel()
        try:
            await health_task
        except asyncio.CancelledError:
            logger.info("🧹 Health monitor task cancelled during shutdown")

    logger.info("🧩 Monitoring service shutdown complete")


@app.get("/health")
async def health():
    """Return cached health results."""
    return JSONResponse(content=last_health_status)


@app.get("/healthz")
async def healthz():
    """Backward-compatible alias for /health"""
    return await health()


@app.get("/metrics")
def metrics():
    """Expose Prometheus metrics."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/")
async def root():
    return {
        "message": "📊 Monitoring Service",
        "monitored_services": list(SERVICES.keys()),
        "check_interval": CHECK_INTERVAL,
        "docs": "/docs",
        "metrics": "/metrics",
        "health": "/health",
        "version": "2.0",
    }


if __name__ == "__main__":
    import uvicorn
    logger.info("🚀 Starting Monitoring Service...")
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("MONITOR_PORT", 8070)))
"""
Monitoring Service — Algo Trading Platform
------------------------------------------
✅ Aggregates health of all microservices
✅ Caches results for faster responses
✅ Tracks latency + availability in Prometheus
✅ Unified JSON logging
"""

import os
import time
import httpx
import asyncio
from datetime import datetime
from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST

from core.utils.logger import get_logger
from core.utils.config_loader import load_config

# -------------------------------------------------
# Initialization
# -------------------------------------------------
logger = get_logger("monitoring_service", json_logs=True)

try:
    CONFIG = load_config("/app/config/config.yaml")
except Exception as e:
    logger.warning(f"⚠️ Could not load config.yaml: {e}")
    CONFIG = {}

DEFAULT_SERVICES = {
    "data_service": os.getenv("DATA_URL", "http://data_service:8080/health"),
    "auth_service": os.getenv("AUTH_URL", "http://auth_service:8018/health"),
}

SERVICES = CONFIG.get("monitoring", {}).get("targets", DEFAULT_SERVICES)
logger.info(f"🩺 Monitoring targets: {list(SERVICES.keys())}")

# -------------------------------------------------
# FastAPI App
# -------------------------------------------------
app = FastAPI(title="Monitoring Service", version="2.0")

# -------------------------------------------------
# Prometheus Metrics
# -------------------------------------------------
service_health = Gauge("service_health_status", "Health status of monitored services", ["service"])
health_checks_total = Counter("health_checks_total", "Total health checks performed", ["service"])
health_check_failures = Counter("health_check_failures_total", "Total health check failures", ["service"])
service_latency = Histogram("service_response_time_seconds", "Latency of monitored services", ["service"])

# -------------------------------------------------
# Cached Health Results
# -------------------------------------------------
last_health_status = {"status": "unknown", "updated_at": None, "services": {}}
CHECK_INTERVAL = int(os.getenv("HEALTH_CHECK_INTERVAL", "30"))

async def perform_health_checks():
    """Perform checks for all registered services."""
    results = {}
    async with httpx.AsyncClient(timeout=3) as client:
        for name, url in SERVICES.items():
            start = time.perf_counter()
            try:
                resp = await client.get(url)
                duration = time.perf_counter() - start
                service_latency.labels(service=name).observe(duration)
                health_checks_total.labels(service=name).inc()

                if resp.status_code == 200:
                    results[name] = {"status": "up", "latency": round(duration, 3)}
                    service_health.labels(service=name).set(1)
                    logger.info(f"✅ {name} is UP ({url}) [{duration:.3f}s]")
                else:
                    results[name] = {"status": f"down ({resp.status_code})"}
                    service_health.labels(service=name).set(0)
                    health_check_failures.labels(service=name).inc()
                    logger.warning(f"⚠️ {name} DOWN ({resp.status_code})")
            except Exception as e:
                results[name] = {"status": "error", "message": str(e)}
                service_health.labels(service=name).set(0)
                health_check_failures.labels(service=name).inc()
                logger.error(f"❌ {name} unreachable ({url}) → {e}")

    overall_status = "healthy" if all(v["status"] == "up" for v in results.values()) else "degraded"
    return {"status": overall_status, "updated_at": datetime.utcnow().isoformat(), "services": results}


@app.on_event("startup")
async def startup_event():
    """Start background health check task."""
    async def scheduler():
        global last_health_status
        while True:
            last_health_status = await perform_health_checks()
            await asyncio.sleep(CHECK_INTERVAL)
    asyncio.create_task(scheduler())
    logger.info("🕒 Background health monitor started (interval=%ss)", CHECK_INTERVAL)


@app.get("/health")
async def health():
    """Return last cached health snapshot."""
    return JSONResponse(content=last_health_status)


@app.get("/metrics")
def metrics():
    """Expose metrics for Prometheus."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/")
async def root():
    """Service metadata endpoint."""
    return {
        "message": "📊 Monitoring Service for Algo Trading Platform",
        "monitored_services": list(SERVICES.keys()),
        "check_interval_sec": CHECK_INTERVAL,
        "metrics": "/metrics",
        "health": "/health",
        "version": "2.0",
    }


if __name__ == "__main__":
    import uvicorn
    logger.info("🚀 Starting Monitoring Service...")
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("MONITOR_PORT", 8070)))
