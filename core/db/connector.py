"""
core/db/connector.py
-----------------------------------------------------
Centralized SQLAlchemy connector for TimescaleDB.
Works in Docker and locally, with retries and logging.
-----------------------------------------------------
"""

import os
import time
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

# -----------------------------------------------------
# Lazy import to prevent circular imports
# -----------------------------------------------------
def safe_imports():
    try:
        from core.utils.config_loader import load_config
        from core.utils.logger import get_logger
        return load_config, get_logger
    except Exception as e:
        print(f"⚠️ Safe import warning (may be early import): {e}")
        return None, lambda name=None: None

load_config, get_logger = safe_imports()
logger = get_logger("core.db") if callable(get_logger) else None

# -----------------------------------------------------
# Load configuration safely
# -----------------------------------------------------
config = {}
if load_config:
    try:
        config = load_config("/app/config/config.yaml")
    except Exception as e:
        if logger:
            logger.warning(f"⚠️ Could not load config file: {e}")
        else:
            print(f"⚠️ Could not load config file: {e}")

# -----------------------------------------------------
# Resolve DB URL
# -----------------------------------------------------
DB_URL = os.getenv("DATABASE_URL") or config.get("database", {}).get("url")
if not DB_URL:
    DB_URL = "postgresql://trader:traderpass@timescaledb:5432/trading"

if logger:
    logger.info(f"🧩 Using Database URL: {DB_URL}")
else:
    print(f"🧩 Using Database URL: {DB_URL}")

# -----------------------------------------------------
# Connection retry logic (for Docker startup timing)
# -----------------------------------------------------
for attempt in range(1, 11):
    try:
        engine = create_engine(DB_URL, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))  # ✅ fixed for SQLAlchemy 2.0+
        if logger:
            logger.info(f"✅ Connected to TimescaleDB on attempt {attempt}")
        else:
            print(f"✅ Connected to TimescaleDB on attempt {attempt}")
        break
    except OperationalError as e:
        if logger:
            logger.warning(f"⚠️ TimescaleDB not ready (attempt {attempt}/10): {e}")
        else:
            print(f"⚠️ TimescaleDB not ready (attempt {attempt}/10): {e}")
        time.sleep(3)
else:
    if logger:
        logger.error("❌ Failed to connect to TimescaleDB after 10 attempts")
    else:
        print("❌ Failed to connect to TimescaleDB after 10 attempts")
    raise RuntimeError("TimescaleDB connection failed")

# -----------------------------------------------------
# Session factory
# -----------------------------------------------------
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

def get_db():
    """Dependency for FastAPI routes."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
