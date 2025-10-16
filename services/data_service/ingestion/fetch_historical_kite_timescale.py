"""
Fetch 6 months of OHLC data from Kite API and store ONLY in TimescaleDB
"""

from datetime import datetime, timedelta
import os
import time
import pandas as pd
from kiteconnect import KiteConnect

from core.utils.logger import get_logger
from core.db.connector import engine
from services.data_service.ingestion.storage import store_live_dataframe

logger = get_logger("data_service.fetch_historical")

# ------------------------------------------------------------------
# Load API credentials (must be set in environment)
# ------------------------------------------------------------------
KITE_API_KEY = os.getenv("KITE_API_KEY")
KITE_ACCESS_TOKEN = os.getenv("KITE_ACCESS_TOKEN")

if not KITE_API_KEY or not KITE_ACCESS_TOKEN:
    raise EnvironmentError("❌ Missing KITE_API_KEY or KITE_ACCESS_TOKEN")

kite = KiteConnect(api_key=KITE_API_KEY)
kite.set_access_token(KITE_ACCESS_TOKEN)

# ------------------------------------------------------------------
# Fetch historical data and store to TimescaleDB
# ------------------------------------------------------------------
def fetch_historical(symbol: str, token: int, days: int = 180, interval: str = "minute"):
    end = datetime.now()
    start = end - timedelta(days=days)
    logger.info(f"📥 Fetching {interval} data for {symbol} from {start} → {end}")

    all_data = []
    batch_days = 30  # Zerodha API supports max 30 days per call

    while start < end:
        batch_end = min(start + timedelta(days=batch_days), end)
        logger.info(f"⏳ Fetching chunk: {start.date()} → {batch_end.date()}")

        try:
            data = kite.historical_data(
                instrument_token=token,
                from_date=start,
                to_date=batch_end,
                interval=interval
            )
            all_data.extend(data)
        except Exception as e:
            logger.error(f"❌ Failed to fetch {start.date()} → {batch_end.date()}: {e}")
        time.sleep(1)  # avoid API rate limit
        start = batch_end

    if not all_data:
        logger.warning("⚠️ No data fetched for this range.")
        return

    df = pd.DataFrame(all_data)
    df["timestamp"] = pd.to_datetime(df["date"])
    df["symbol"] = symbol   # ✅ <-- FIX: Add symbol column explicitly
    df = df[["symbol", "timestamp", "open", "high", "low", "close", "volume"]]

    logger.info(f"💾 Storing {len(df)} rows in TimescaleDB...")
    store_live_dataframe(df, source="historical_kite")
    logger.info(f"✅ Stored {len(df)} rows for {symbol} successfully.")


# ------------------------------------------------------------------
# Entrypoint
# ------------------------------------------------------------------
if __name__ == "__main__":
    fetch_historical("NIFTY50", 256265, days=180, interval="minute")
    logger.info("✅ Historical data load complete (TimescaleDB only).")
