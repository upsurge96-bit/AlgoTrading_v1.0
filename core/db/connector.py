"""
core/db/connector.py
-----------------------------------------------------
Centralized SQLAlchemy connector for TimescaleDB.
Works in Docker and locally, with retries and logging.
-----------------------------------------------------
"""

import os
import time
import threading
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker, Session
from urllib.parse import urlsplit, urlunsplit
from typing import Dict, Any, Optional, Generator

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

if logger:
    logger.info(f"🧩 Using Database URL: {_redact_dsn(DB_URL)}")
else:
    print(f"🧩 Using Database URL: {_redact_dsn(DB_URL)}")

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

def get_db() -> Generator[Session, None, None]:
    """Dependency for FastAPI routes."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# -----------------------------------------------------
# Database connector class
# -----------------------------------------------------
class DatabaseConnector:
    """
    Database connector for service-level database operations.
    
    Provides a thread-local session for safe multi-threaded use
    and convenience methods for database operations.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton pattern to ensure only one connection pool is created."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(DatabaseConnector, cls).__new__(cls)
                cls._instance._initialize()
            return cls._instance
    
    def _initialize(self):
        """Initialize the connector with a thread-local session."""
        self._thread_local = threading.local()
        self._thread_local.session = None
        self._setup_completed = False
        
        # Store engine and session factory
        self.engine = engine
        self.SessionLocal = SessionLocal
    
    @property
    def session(self) -> Session:
        """
        Get a thread-local session.
        
        Returns:
            SQLAlchemy session
        """
        if not hasattr(self._thread_local, "session") or self._thread_local.session is None:
            self._thread_local.session = self.SessionLocal()
            
        return self._thread_local.session
    
    def close_session(self) -> None:
        """Close the thread-local session."""
        if hasattr(self._thread_local, "session") and self._thread_local.session is not None:
            self._thread_local.session.close()
            self._thread_local.session = None
    
    def execute_query(self, query_text: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """
        Execute a raw SQL query.
        
        Args:
            query_text: SQL query text
            params: Query parameters
            
        Returns:
            Query result
        """
        try:
            with self.engine.connect() as conn:
                stmt = text(query_text)
                if params:
                    result = conn.execute(stmt, params)
                else:
                    result = conn.execute(stmt)
                return result.fetchall()
        except Exception as e:
            if logger:
                logger.error(f"Query execution error: {e}")
            raise
    
    def execute_transaction(self, callback):
        """
        Execute a callback function within a transaction.
        
        Args:
            callback: Function that takes a session parameter
            
        Returns:
            Result of the callback function
        """
        session = self.session
        try:
            result = callback(session)
            session.commit()
            return result
        except Exception as e:
            session.rollback()
            if logger:
                logger.error(f"Transaction error: {e}")
            raise
        finally:
            # Do not close the session here to allow for multi-operation transactions
            pass
    
    def begin_transaction(self):
        """
        Begin a new transaction.
        
        Returns:
            Self, for method chaining
        """
        self.session.begin_nested()
        return self
    
    def commit(self):
        """Commit the current transaction."""
        self.session.commit()
    
    def rollback(self):
        """Rollback the current transaction."""
        self.session.rollback()
    
    def __enter__(self):
        """Context manager entry point."""
        self.begin_transaction()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit point."""
        if exc_type is not None:
            self.rollback()
        else:
            try:
                self.commit()
            except Exception:
                self.rollback()
                raise
    
    def __del__(self):
        """Clean up resources when the object is garbage collected."""
        self.close_session()
