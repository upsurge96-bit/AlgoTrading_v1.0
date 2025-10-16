import io
import time
import pandas as pd
from sqlalchemy import text, Table, MetaData
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from minio import Minio

from core.utils.config_loader import load_config
from core.utils.logger import get_logger
from core.db.connector import engine, get_db  # centralized connector

logger = get_logger("data_service.storage")
CFG = load_config("/app/config/config.yaml")

# ------------------------------------------------------------
# 🪣 MinIO setup
# ------------------------------------------------------------
MINIO_CFG = CFG.get("minio", {})
MINIO_ENDPOINT = MINIO_CFG.get("endpoint", "minio:9000")
MINIO_ACCESS = MINIO_CFG.get("access_key", "minioaccess")
MINIO_SECRET = MINIO_CFG.get("secret_key", "miniopass")
MINIO_BUCKET = MINIO_CFG.get("bucket", "historical-data")

minio_client = Minio(
    endpoint=MINIO_ENDPOINT,
    access_key=MINIO_ACCESS,
    secret_key=MINIO_SECRET,
    secure=MINIO_CFG.get("secure", False),
)


# ------------------------------------------------------------
# 🧱 TimescaleDB Table Management
# ------------------------------------------------------------
def ensure_timescale_table():
    """
    Ensures TimescaleDB hypertable and time dimension columns exist.
    Creates or upgrades 'live_market_data' safely.
    """
    logger.debug("🧱 Ensuring TimescaleDB table 'live_market_data' schema is valid...")

    try:
        with engine.begin() as conn:
            # ✅ 1️⃣ Create table if missing
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS live_market_data (
                    symbol TEXT NOT NULL,
                    timestamp TIMESTAMPTZ NOT NULL,
                    open DOUBLE PRECISION,
                    high DOUBLE PRECISION,
                    low DOUBLE PRECISION,
                    close DOUBLE PRECISION,
                    volume DOUBLE PRECISION,
                    source TEXT,
                    CONSTRAINT live_market_data_pkey PRIMARY KEY (symbol, timestamp)
                );
            """))

            # ✅ 2️⃣ Add new time-dimension columns if missing
            for col_def in [
                ("year", "INTEGER"),
                ("month", "INTEGER"),
                ("week", "INTEGER"),
                ("date", "DATE"),
                ("hour", "INTEGER"),
            ]:
                col, dtype = col_def
                conn.execute(
                    text(f"""
                        DO $$
                        BEGIN
                            IF NOT EXISTS (
                                SELECT 1
                                FROM information_schema.columns
                                WHERE table_name = 'live_market_data' AND column_name = '{col}'
                            ) THEN
                                ALTER TABLE live_market_data ADD COLUMN {col} {dtype};
                            END IF;
                        END $$;
                    """)
                )

            # ✅ 3️⃣ Ensure hypertable exists
            try:
                conn.execute(
                    text("SELECT create_hypertable('live_market_data', 'timestamp', if_not_exists => TRUE);")
                )
                logger.debug("✅ Hypertable verified/created successfully.")
            except Exception as e:
                logger.debug("ℹ️ Hypertable creation skipped or already exists: %s", e)

    except Exception as e:
        logger.exception("❌ Failed to ensure Timescale table or schema upgrade: %s", e)
        raise



# ------------------------------------------------------------
# 💾 Smart Store Function (auto detects live vs historical)
# ------------------------------------------------------------
def store_dataframe(df: pd.DataFrame, source: str = "kite_ws"):
    """
    Automatically chooses the correct storage method:
    - If data is recent (< 24h old) ➜ UPSERT (real-time)
    - If data is old ➜ BULK INSERT (historical)

    This function keeps additional time-dimension columns (year, month, week, date, hour)
    for historical bulk inserts but filters them out for live upserts to avoid schema
    mismatches. It also validates required columns and removes exact duplicates prior to
    bulk load.
    """
    if df is None or df.empty:
        logger.warning("⚠️ Empty DataFrame received — skipping TimescaleDB insert.")
        return

    df2 = df.copy()
    if df2["timestamp"].dtype in ["int64", "float64"]:
        df2["timestamp"] = pd.to_datetime(df2["timestamp"], unit="ms", utc=True)
    else:
        # ensure timezone-aware timestamps for consistency
        df2["timestamp"] = pd.to_datetime(df2["timestamp"]).dt.tz_convert("UTC") if pd.api.types.is_datetime64_any_dtype(df2["timestamp"]) else pd.to_datetime(df2["timestamp"], utc=True)

    df2["source"] = source

    # Decide mode: live or historical
    latest_ts = pd.to_datetime(df2["timestamp"].max())
    is_historical = (pd.Timestamp.utcnow() - latest_ts).total_seconds() > 86400

    if is_historical:
        # For historical loads keep partitioning/time-dimension columns if provided by caller
        hist_df = df2.copy()
        # Ensure required columns exist
        if "symbol" not in hist_df.columns:
            logger.error("❌ Historical insert requested but 'symbol' column is missing in DataFrame")
            raise ValueError("'symbol' column is required for historical inserts")

        # Deduplicate exact (symbol, timestamp) pairs to avoid unique constraint violations
        if {"symbol", "timestamp"}.issubset(hist_df.columns):
            before = len(hist_df)
            hist_df = hist_df.drop_duplicates(subset=["symbol", "timestamp"])
            after = len(hist_df)
            if before != after:
                logger.debug("🔁 Dropped %d duplicate rows before historical insert", before - after)

        # Make sure Timescale table & time-dimension columns exist before bulk insert
        ensure_timescale_table()
        _insert_historical(hist_df, source)
    else:
        # Live path: only keep columns matching the core schema to avoid insert errors
        expected_cols = ["symbol", "timestamp", "open", "high", "low", "close", "volume", "source"]
        live_df = df2[[c for c in df2.columns if c in expected_cols]]
        # Validate presence of required columns for upsert
        if "symbol" not in live_df.columns:
            logger.error("❌ Live upsert requested but 'symbol' column is missing in DataFrame")
            raise ValueError("'symbol' column is required for live upserts")

        ensure_timescale_table()
        _upsert_live(live_df, source)


# ------------------------------------------------------------
# 🔁 UPSERT for live ticks
# ------------------------------------------------------------
def _upsert_live(df: pd.DataFrame, source: str):
    start_time = time.time()
    try:
        metadata = MetaData()
        table = Table("live_market_data", metadata, autoload_with=engine)

        insert_stmt = insert(table)
        upsert_stmt = insert_stmt.on_conflict_do_update(
            index_elements=["symbol", "timestamp"],
            set_={
                "open": insert_stmt.excluded.open,
                "high": insert_stmt.excluded.high,
                "low": insert_stmt.excluded.low,
                "close": insert_stmt.excluded.close,
                "volume": insert_stmt.excluded.volume,
                "source": insert_stmt.excluded.source,
            }
        )

        records = df.to_dict(orient="records")

        with engine.begin() as conn:
            conn.execute(upsert_stmt, records)

        duration = round(time.time() - start_time, 2)
        logger.info(
            "💾 [LIVE] Upserted %d rows into TimescaleDB | source=%s | duration=%ss",
            len(df),
            source,
            duration,
        )

    except SQLAlchemyError as e:
        logger.exception("❌ SQLAlchemy error during live UPSERT: %s", e)
        raise
    except Exception as e:
        logger.exception("❌ Unexpected error during live UPSERT: %s", e)
        raise


# ------------------------------------------------------------
# 🕰️ Fast bulk insert for historical data
# ------------------------------------------------------------
def _insert_historical(df: pd.DataFrame, source: str):
    start_time = time.time()
    try:
        # Defensive checks: ensure required columns and remove rows missing critical values
        if df is None or df.empty:
            logger.warning("⚠️ Empty DataFrame received for historical insert — skipping.")
            return

        if "symbol" not in df.columns or "timestamp" not in df.columns:
            logger.error("❌ Historical insert requires 'symbol' and 'timestamp' columns")
            raise ValueError("'symbol' and 'timestamp' are required for historical inserts")

        # Ensure table/columns exist (idempotent)
        ensure_timescale_table()

        with engine.begin() as conn:
            # let pandas handle insertion; keep extra time-dimension columns if present
            df.to_sql(
                "live_market_data",
                conn,
                if_exists="append",
                index=False,
                method="multi",
                chunksize=5000,
            )

        duration = round(time.time() - start_time, 2)
        logger.info(
            "📦 [HISTORICAL] Inserted %d rows into TimescaleDB | source=%s | duration=%ss",
            len(df),
            source,
            duration,
        )

    except SQLAlchemyError as e:
        logger.exception("❌ SQLAlchemy error during historical insert: %s", e)
        raise
    except Exception as e:
        logger.exception("❌ Unexpected error during historical insert: %s", e)
        raise


# ------------------------------------------------------------
# 📤 Save historical Parquet data to MinIO
# ------------------------------------------------------------
def save_historical_parquet(df: pd.DataFrame, symbol: str, prefix: str = "historical"):
    """
    Saves a DataFrame as Parquet and uploads it to MinIO under:
      {prefix}/{symbol}/{symbol}_{timestamp}.parquet
    """
    if df is None or df.empty:
        logger.warning("⚠️ Empty DataFrame received — skipping MinIO upload.")
        return None

    start_time = time.time()
    date_str = pd.to_datetime(df["timestamp"].iloc[-1]).strftime("%Y%m%d%H%M%S")
    object_name = f"{prefix}/{symbol}/{symbol}_{date_str}.parquet"

    # Convert DataFrame to Parquet in memory
    buffer = io.BytesIO()
    try:
        df.to_parquet(buffer, index=False)
    except Exception as e:
        logger.exception("❌ Failed to serialize DataFrame to Parquet: %s", e)
        raise
    buffer.seek(0)
    size_bytes = len(buffer.getvalue())

    # Ensure MinIO bucket exists
    try:
        if not minio_client.bucket_exists(MINIO_BUCKET):
            logger.info("🪣 MinIO bucket '%s' not found — creating it...", MINIO_BUCKET)
            minio_client.make_bucket(MINIO_BUCKET)
            logger.info("✅ Created MinIO bucket '%s'", MINIO_BUCKET)
    except Exception as e:
        logger.exception("❌ Failed to verify or create MinIO bucket: %s", e)
        raise

    # Upload to MinIO
    try:
        minio_client.put_object(MINIO_BUCKET, object_name, buffer, length=size_bytes)
        duration = round(time.time() - start_time, 2)
        logger.info(
            "📤 Uploaded Parquet to MinIO | object=%s | size=%.2f KB | duration=%ss",
            object_name,
            size_bytes / 1024,
            duration,
        )
        return object_name
    except Exception as e:
        logger.exception("❌ Failed to upload Parquet to MinIO: %s", e)
        raise


# Compatibility alias: older modules import `store_live_dataframe`
# Keep it pointing to the new `store_dataframe` implementation.
store_live_dataframe = store_dataframe

