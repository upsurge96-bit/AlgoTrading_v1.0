from fastapi import FastAPI
from core.utils.logger import get_logger
from core.utils.config_loader import load_config
import uvicorn

logger = get_logger("risk_service")
config = load_config("/app/config/config.yaml")
app = FastAPI(title="Risk Service")

@app.get("/health")
def health():
    return {"status": "ok", "service": "risk-service"}

@app.on_event("startup")
async def startup_event():
    logger.info("🧠 Risk Service starting...")
    logger.info(f"Loaded config keys: {list(config.keys())}")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("🧠 Risk Service shutting down...")

if __name__ == "__main__":
    port = int(config.get("api", {}).get("port", 8020))
    logger.info(f"🚀 Risk Service running on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
