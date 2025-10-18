"""
Dummy Service Template
---------------------------------------------------------
Temporary FastAPI service for Prometheus/Grafana testing.
Exposes:
  - /                : basic service info
  - /healthz         : simple liveness probe
  - /metrics         : Prometheus metrics endpoint
---------------------------------------------------------
"""

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
import os

# Service name (can be passed as ENV)
SERVICE_NAME = os.getenv("SERVICE_NAME", "dummy_service")

# Initialize FastAPI
app = FastAPI(title=SERVICE_NAME, version="0.1")

# Initialize Prometheus metrics exporter
instrumentator = Instrumentator().instrument(app).expose(app)

@app.get("/")
def root():
    return {"service": SERVICE_NAME, "status": "ok"}

@app.get("/health")
def health():
    return {"service": SERVICE_NAME, "status": "healthy"}


@app.get("/healthz")
def healthz():
    """Backward-compatible alias for /health"""
    return health()

# Optional: custom dummy metrics (you can remove or extend)
from prometheus_client import Counter

dummy_counter = Counter("dummy_requests_total", "Total dummy requests")

@app.get("/ping")
def ping():
    dummy_counter.inc()
    return {"message": f"{SERVICE_NAME} pong!"}
