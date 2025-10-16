# services/data_service/archiver.py

import pandas as pd
import time
from datetime import datetime, timedelta, timezone
from sqlalchemy import text
from core.utils.logger import get_logger
from core.utils.config_loader import load_config
from services.data_service.ingestion.storage import engine, save_historical_parquet

logger = get_logger("data_service.ingester")
CFG = load_config("/app/config/config.yaml")

RETENTION_DAYS = CFG.get("retention", {}).get("timescale_days", 90)
ARCHIVE_YEARS = CFG.get("retention", {}).get("minio_years", 5)


def archive_old_data(symbol: str):
    """Archive data older than RETENTION_DAYS from TimescaleDB to MinIO."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)
    logger.info("🗂️ Archiving data older than %s for %s", cutoff, symbol)

    try:
        query = text("""
            SELECT * FROM live_market_data
            WHERE symbol = :symbol AND timestamp < :cutoff
            ORDER BY timestamp
        """)
        df = pd.read_sql(query, engine, params={"symbol": symbol, "cutoff": cutoff})
        if df.empty:
            logger.info("ℹ️ No old data to archive for %s", symbol)
            return

        object_name = save_historical_parquet(df, symbol, prefix="archive")
        logger.info("✅ Archived %d rows to MinIO (%s)", len(df), object_name)

        with engine.begin() as conn:
            conn.execute(text("""
                DELETE FROM live_market_data
                WHERE symbol = :symbol AND timestamp < :cutoff
            """), {"symbol": symbol, "cutoff": cutoff})
        logger.info("🧹 Deleted archived rows from TimescaleDB for %s", symbol)

    except Exception as e:
        logger.exception("❌ Archival process failed for %s: %s", symbol, e)


def incremental_minio_load(symbol: str, start_date: str, end_date: str):
    """Load historical data incrementally to MinIO."""
    import ccxt

    exchange = ccxt.binance({"enableRateLimit": True})
    timeframe = "1d"
    since = int(pd.Timestamp(start_date).timestamp() * 1000)
    end_ts = int(pd.Timestamp(end_date).timestamp() * 1000)

    logger.info("📦 Starting incremental backfill for %s (%s → %s)", symbol, start_date, end_date)

    while since < end_ts:
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=1000)
            if not ohlcv:
                break
            df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
            save_historical_parquet(df, symbol, prefix="historical")
            logger.info("📤 Uploaded batch to MinIO | rows=%d | up_to=%s", len(df), df['timestamp'].iloc[-1])
            since = int(df["timestamp"].iloc[-1].timestamp() * 1000) + 60000
            time.sleep(0.5)
        except Exception as e:
            logger.exception("⚠️ Incremental batch load failed: %s", e)
            time.sleep(3)

    logger.info("🏁 Completed incremental MinIO load for %s", symbol)
