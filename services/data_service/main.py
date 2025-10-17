"""
Data Service — clean entrypoint
Provides configuration and lightweight API surface for the data service.
This file intentionally does NOT start the Kite WebSocket client; that runs in a separate worker/process.
"""

import os
from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from core.utils.logger import get_logger
from core.utils.config_loader import load_config

# Initialize logger and config
logger = get_logger("data_service")
try:
    CONFIG = load_config("/app/config/config.yaml")
    logger.info("✅ Loaded config from: /app/config/config.yaml")
except Exception as e:
    logger.warning(f"⚠️ Could not load config.yaml: {e}")
    CONFIG = {}

# FastAPI app
app = FastAPI(title="Data Service", version="1.0")

# Mount API routes if available
try:
    from services.data_service.api.routes import router as api_router
    app.include_router(api_router, prefix="")
    logger.info("📦 Mounted data service API routes")
except Exception:
    logger.debug("No API routes to mount or failed to import routes")


@app.get("/health")
async def health():
    """Simple health endpoint for Kubernetes / load balancers."""
    return JSONResponse(content={"status": "ok", "service": "data_service"})


@app.get("/metrics")
def metrics():
    """Expose Prometheus metrics (if any are registered)."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/")
def root():
    return {"service": "data_service", "version": "1.0"}


if __name__ == "__main__":
    import uvicorn
    logger.info("🚀 Starting Data Service (no Kite client)...")
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("DATA_PORT", 8080)))
