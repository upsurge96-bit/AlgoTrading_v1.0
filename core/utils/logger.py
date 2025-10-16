"""
logger.py
-------------------------------------------------
Global logging configuration for all Algo-Trading Platform services.
Writes both to console (stdout) and a daily rotating log file
so Promtail/Loki can collect structured logs.

Usage:
    from core.utils.logger import get_logger
    logger = get_logger("data_service")
-------------------------------------------------
"""

import logging
import os
import sys
from datetime import datetime


def get_logger(name: str = "app", level=logging.INFO) -> logging.Logger:
    """
    Unified logger:
      • Console (stdout)
      • File: {LOG_DIR}/{SERVICE_NAME}_{YYYYMMDD}.log
    """

    # ------------------------------------------------------------------
    # Directory setup
    # ------------------------------------------------------------------
    log_dir = os.getenv("LOG_DIR", os.path.join(os.getcwd(), "logs"))
    os.makedirs(log_dir, exist_ok=True)

    service_name = os.getenv("SERVICE_NAME", name)
    date_str = datetime.utcnow().strftime("%Y%m%d")
    log_path = os.path.join(log_dir, f"{service_name}_{date_str}.log")

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------
    file_handler = logging.FileHandler(log_path, mode="a", encoding="utf-8")
    console_handler = logging.StreamHandler(sys.stdout)

    fmt = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    formatter = logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S")

    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger = logging.getLogger(service_name)
    logger.setLevel(level)

    # Avoid duplicate handlers
    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    logger.propagate = False

    # Instant flush in Docker
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)
        sys.stderr.reconfigure(line_buffering=True)

    # Confirm startup path
    logger.info(f"📂 Logging initialized → {log_path}")

    return logger
