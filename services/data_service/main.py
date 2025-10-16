# services/data-service/main.py
from fastapi import FastAPI, APIRouter, Response
from fastapi.responses import JSONResponse
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST

from core.utils.logger import get_logger
from core.utils.config_loader import load_config
from services.data_service.api.routes import router as data_router
from services.data_service.ingestion.scheduler import start_scheduler
from services.data_service.ingestion.storage import ensure_timescale_table
from services.data_service.ingestion.subscriber import start_consumer_in_background  # ✅ NEW
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
import time
import uvicorn
import asyncio
import time
import os  # ✅ ADD THIS LINE

# -------------------------------------------------
# Initialization
# -------------------------------------------------
logger = get_logger("data_service")
logger.info("🚀 Initializing Data Service...")

try:
    config = load_config("/app/config/config.yaml")
    logger.info("⚙️ Configuration loaded successfully")
except Exception as e:
    logger.exception("❌ Failed to load configuration: %s", e)
    raise

app = FastAPI(title="Data Ingestion Service", version="1.0")

# -------------------------------------------------
# API Routes
# -------------------------------------------------
app.include_router(data_router, prefix="/data", tags=["data"])

router = APIRouter()

@router.get("/healthz", tags=["system"])
async def health_check():
    """Basic health check endpoint for Monitoring and Prometheus."""
    return JSONResponse(content={"status": "ok"}, status_code=200)

# Mount system router
app.include_router(router)
logger.info("🩺 Health check route registered at /healthz")

# -------------------------------------------------
# Prometheus Metrics
# -------------------------------------------------
ingestion_counter = Counter("data_ingestion_total", "Number of successful data ingestions")
kafka_messages_consumed = Counter("kafka_messages_consumed_total", "Total Kafka messages consumed")  # ✅ NEW

@app.get("/metrics")
def metrics():
    """Expose Prometheus metrics."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# ------------------------------------------------------------
# ✅ Database connection health check at startup
# ------------------------------------------------------------

def verify_db_connection():
    db_url = os.getenv("DATABASE_URL")
    logger.info(f"🧩 Checking DB connectivity → {db_url}")
    for attempt in range(5):
        try:
            engine = create_engine(db_url)
            with engine.connect() as conn:
                logger.info("✅ Successfully connected to TimescaleDB!")
                return True
        except OperationalError as e:
            logger.warning(f"⏳ Database not ready yet (attempt {attempt+1}/5): {e}")
            time.sleep(5)
    logger.error("💥 Failed to connect to TimescaleDB after multiple retries.")
    return False

# Run this before scheduler/kafka startup
verify_db_connection()

# Run this before scheduler/kafka startup
verify_db_connection()


# -------------------------------------------------
# Lifecycle Events
# -------------------------------------------------
@app.on_event("startup")
async def startup_event():
    logger.info("📡 Data Service startup event triggered")
    start_time = time.time()

    # Initialize TimescaleDB
    try:
        logger.info("🧱 Ensuring TimescaleDB tables exist...")
        ensure_timescale_table()
        logger.info("✅ TimescaleDB tables ready")
    except Exception as e:
        logger.warning("⚠️ Timescale initialization failed: %s", e, exc_info=True)

    # Start scheduler
    try:
        logger.info("⏱️ Launching ingestion scheduler (non-blocking)...")
        start_scheduler()
        logger.info("✅ Scheduler successfully started")
    except Exception as e:
        logger.exception("❌ Failed to start scheduler: %s", e)

    # Start Kafka consumer
    try:
        logger.info("📨 Launching Kafka consumer (non-blocking)...")
        start_consumer_in_background()
        logger.info("✅ Kafka consumer started successfully")
    except Exception as e:
        logger.exception("❌ Failed to start Kafka consumer: %s", e)

    elapsed = round(time.time() - start_time, 2)
    logger.info("✅ Data Service startup completed in %ss", elapsed)

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("🛑 Data Service shutdown initiated...")
    await asyncio.sleep(0.1)
    logger.info("✅ Data Service shutdown complete")

# -------------------------------------------------
# Entrypoint
# -------------------------------------------------
if __name__ == "__main__":
    port = int(config.get("api", {}).get("port", 8080))
    logger.info("🌍 Starting Data Service on host 0.0.0.0:%d", port)
    try:
        uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
    except Exception as e:
        logger.exception("💥 Uvicorn failed to start: %s", e)
        raise
