from fastapi import FastAPI
from core.utils.logger import get_logger
from core.utils.config_loader import load_config
import uvicorn

logger = get_logger("execution_service")
config = load_config("/app/config/config.yaml")
app = FastAPI(title="Execution Service")

@app.get("/health")
def health():
    return {"status": "ok", "service": "execution-service"}

@app.on_event("startup")
async def startup_event():
    logger.info("💸 Execution Service booting...")
    broker = config.get("kafka", {}).get("brokers", [])
    db_url = config.get("database", {}).get("url")
    logger.info(f"Connected to DB: {db_url}")
    logger.info(f"Kafka brokers: {broker}")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("💸 Execution Service shutting down...")

if __name__ == "__main__":
    port = int(config.get("api", {}).get("port", 8030))
    logger.info(f"🚀 Execution Service running on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
