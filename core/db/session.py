from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.utils.config_loader import load_config
import os
from core.utils.logger import get_logger

logger = get_logger("core.db")

# Load config file
config = load_config("/app/config/config.yaml")

# ✅ Always prioritize environment variable first
DB_URL = os.getenv("DATABASE_URL")

# Fallback to config.yaml (if defined)
if not DB_URL:
    DB_URL = config.get("database", {}).get("url")

# Final fallback (for local dev)
if not DB_URL:
    DB_URL = "postgresql://trader:traderpass@timescaledb:5432/trading"

logger.info(f"🧩 Using Database URL: {DB_URL}")

engine = create_engine(DB_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
