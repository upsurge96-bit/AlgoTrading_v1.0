"""
logger.py
-------------------------------------------------
Global logging configuration for all Algo-Trading Platform services.
Supports:
  • Console + Rotating file output
  • JSON logs (for Promtail/Loki ingestion)
  • IST timestamps
-------------------------------------------------
Usage:
    from core.utils.logger import get_logger
    logger = get_logger("data_service")
-------------------------------------------------
"""

import logging
import os
import json
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from logging.handlers import RotatingFileHandler

import sys
from zoneinfo import ZoneInfo                                                                                                                                       

IST = ZoneInfo("Asia/Kolkata")
_logging_initialized = False

class JSONFormatter(logging.Formatter):
    """Structured JSON log formatter for Promtail/Loki ingestion."""

    def format(self, record):
        log_data = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "service": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_data)

    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, IST)
        return dt.strftime(datefmt or "%Y-%m-%d %H:%M:%S")


def get_logger(name="app", level=logging.INFO, json_logs: bool = False) -> logging.Logger:
    global _logging_initialized
    logger = logging.getLogger(name)

    if not _logging_initialized:
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        logger.setLevel(getattr(logging, log_level, logging.INFO))

        for h in logger.handlers[:]:
            logger.removeHandler(h)

        # --- Formatter ---
        if json_logs:
            formatter = JSONFormatter()
        else:
            formatter = logging.Formatter(
                "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            formatter.converter = lambda *args: datetime.now(IST).timetuple()

        # --- Console (stdout) handler ---
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # --- Optional rotating file handler ---
        # Priority:
        # 1. LOG_FILE env var (explicit)
        # 2. Use LOG_DIR (or LOG_PATH) + SERVICE_NAME (env) or logger name
        # 3. Fall back to repo-local `logs/<name>.log`
        log_file = os.getenv("LOG_FILE")

        if not log_file:
            log_dir = os.getenv("LOG_DIR") or os.getenv("LOG_PATH") or "logs"
            service_env = os.getenv("SERVICE_NAME")
            service_name = service_env or name or "app"
            # ensure filename is service-specific
            log_file = os.path.join(log_dir, f"{service_name}.log")

        try:
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            file_handler = RotatingFileHandler(log_file, maxBytes=10_000_000, backupCount=5)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
            logger.info(f"\U0001F4C2 File logging enabled: {log_file}")
        except Exception as e:
            # If file handler can't be created (permissions, invalid path), continue with console only
            logger.warning(f"Could not initialize file handler at {log_file}: {e}")

        _logging_initialized = True
        logger.info("📂 Logging initialized (stdout + optional file)")

    return logger
