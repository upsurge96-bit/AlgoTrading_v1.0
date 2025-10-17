from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.utils.config_loader import load_config
import os
from core.utils.logger import get_logger
from urllib.parse import urlsplit, urlunsplit  # <-- added

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

def _redact_dsn(dsn: str) -> str:
    try:
        u = urlsplit(dsn)
        if u.password is None:
            return dsn
        netloc = f"{u.username}:***@{u.hostname}"
        if u.port:
            netloc += f":{u.port}"
        return urlunsplit((u.scheme, netloc, u.path, u.query, u.fragment))
    except Exception:
        return dsn

logger.info(f"🧩 Using Database URL: {_redact_dsn(DB_URL)}")

engine = create_engine(DB_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
