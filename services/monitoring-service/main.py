"""
Monitoring Service — Algo Trading Platform
------------------------------------------
✅ Aggregates health of all microservices
✅ Exposes Prometheus metrics
✅ Unified logging via core.logger
✅ Configurable targets via config.yaml
"""

from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse
import httpx
import os
from prometheus_client import Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST

from core.utils.logger import get_logger
from core.utils.config_loader import load_config

# -------------------------------------------------
# Initialize
# -------------------------------------------------
logger = get_logger("monitoring_service")

try:
    CONFIG = load_config("/app/config/config.yaml")
except Exception as e:
    logger.warning(f"⚠️ Could not load config.yaml: {e}")
    CONFIG = {}

logger.info("✅ Configuration loaded for Monitoring Service")

# -------------------------------------------------
# Load monitored targets
# -------------------------------------------------
DEFAULT_SERVICES = {
    "data_service": os.getenv("DATA_URL", "http://data-service:8010/health"),
    "strategy_service": os.getenv("STRATEGY_URL", "http://strategy-service:8020/health"),
    "execution_service": os.getenv("EXEC_URL", "http://execution-service:8030/health"),
    "risk_service": os.getenv("RISK_URL", "http://risk-service:8040/health"),
    "auth_service": os.getenv("AUTH_URL", "http://auth-service:8060/health"),
}

SERVICES = CONFIG.get("monitoring", {}).get("targets", DEFAULT_SERVICES)
logger.info(f"🩺 Monitoring targets: {list(SERVICES.keys())}")

# -------------------------------------------------
# FastAPI App
# -------------------------------------------------
app = FastAPI(title="Monitoring Service", version="1.0")

# -------------------------------------------------
# Prometheus Metrics
# -------------------------------------------------
service_health = Gauge("service_health_status", "Health status of monitored services", ["service"])
health_checks_total = Counter("health_checks_total", "Total health checks performed", ["service"])
health_check_failures = Counter("health_check_failures_total", "Total health check failures", ["service"])

# -------------------------------------------------
# Health Aggregation Endpoint
# -------------------------------------------------
@app.get("/health")
async def global_health():
    """
    Performs health checks for all registered services.
    Returns per-service status and Prometheus metrics.
    """
    results = {}
    async with httpx.AsyncClient(timeout=3) as client:
        for name, url in SERVICES.items():
            try:
                resp = await client.get(url)
                health_checks_total.labels(service=name).inc()

                if resp.status_code == 200:
                    results[name] = "up"
                    service_health.labels(service=name).set(1)
                    logger.info(f"✅ {name} is UP ({url})")
                else:
                    results[name] = f"down ({resp.status_code})"
                    service_health.labels(service=name).set(0)
                    health_check_failures.labels(service=name).inc()
                    logger.warning(f"⚠️ {name} DOWN ({resp.status_code})")

            except Exception as e:
                results[name] = f"error: {str(e)}"
                service_health.labels(service=name).set(0)
                health_check_failures.labels(service=name).inc()
                logger.error(f"❌ {name} unreachable ({url}) → {e}")

    overall_status = "healthy" if all(v == "up" for v in results.values()) else "degraded"
    logger.info(f"🔍 Aggregated health status: {overall_status}")
    return JSONResponse(content={"status": overall_status, "services": results})

# -------------------------------------------------
# Prometheus Metrics Endpoint
# -------------------------------------------------
@app.get("/metrics")
def metrics():
    """Expose metrics in Prometheus format."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

# -------------------------------------------------
# Root Summary Endpoint
# -------------------------------------------------
@app.get("/")
async def root():
    """Root info endpoint."""
    return {
        "message": "📊 Monitoring Service for Algo Trading Platform",
        "monitored_services": list(SERVICES.keys()),
        "docs": "/docs",
        "metrics": "/metrics",
        "health": "/health"
    }

# -------------------------------------------------
# Run standalone
# -------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    logger.info("🚀 Starting Monitoring Service...")
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("MONITOR_PORT", 8070)))
