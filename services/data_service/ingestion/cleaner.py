import pandas as pd
from core.utils.logger import get_logger

logger = get_logger("data_service.cleaner")

def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Cleans a raw market DataFrame.

    Steps:
    1. Remove duplicate timestamps
    2. Sort by timestamp
    3. Convert timestamps to UTC datetime
    4. Forward-fill missing values
    5. Log summary of cleaning results
    """

    if df is None or df.empty:
        logger.warning("⚠️ Received empty DataFrame for cleaning.")
        return pd.DataFrame()

    initial_rows = len(df)
    logger.debug("🧹 Starting DataFrame cleaning | initial_rows=%d", initial_rows)

    # Ensure timestamp column exists
    if "timestamp" not in df.columns:
        logger.error("❌ DataFrame missing required 'timestamp' column.")
        raise ValueError("Missing 'timestamp' column in DataFrame")

    # Drop duplicate timestamps
    df = df.drop_duplicates(subset=["timestamp"])
    logger.debug("🧽 Removed duplicates | rows_after=%d", len(df))

    # Sort by timestamp
    df = df.sort_values("timestamp")

    # Convert timestamp to UTC datetime
    try:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    except Exception as e:
        logger.exception("❌ Failed to parse timestamps: %s", e)
        raise

    # Fill missing values (forward-fill)
    df = df.fillna(method="ffill")

    final_rows = len(df)
    logger.info(
        "✅ Cleaned DataFrame | rows_before=%d | rows_after=%d | columns=%d",
        initial_rows, final_rows, len(df.columns)
    )

    return df
