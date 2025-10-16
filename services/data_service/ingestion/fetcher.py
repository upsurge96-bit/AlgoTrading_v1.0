# services/data-service/ingestion/fetcher.py

import ccxt
import pandas as pd
import time
from core.utils.logger import get_logger
from core.utils.retry import retry
from services.data_service.ingestion.publisher import publish_market_data
from services.data_service.ingestion.storage import store_live_dataframe, save_historical_parquet
from core.utils.config_loader import load_config
from kiteconnect import KiteConnect

logger = get_logger("data_service.fetcher")
CFG = load_config("/app/config/config.yaml")


@retry(Exception, tries=4, delay=1, backoff=2)
def fetch_historical_ccxt(symbol: str, timeframe: str = "1m", limit: int = 500):
    """
    Fetch OHLCV data from Binance using ccxt, then:
      - Convert to DataFrame
      - Publish each record to Kafka
      - Store live data in TimescaleDB
      - Save historical snapshot to MinIO
    """
    start_time = time.time()
    logger.info(
        "📡 Starting CCXT fetch | symbol=%s | timeframe=%s | limit=%d",
        symbol, timeframe, limit
    )

    try:
        # Initialize exchange
        exchange = ccxt.binance({"enableRateLimit": True})
        logger.debug("🔗 Binance exchange client initialized")

        # Fetch OHLCV data
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        logger.info("✅ Received %d candles for %s [%s]", len(ohlcv), symbol, timeframe)

        # Transform into DataFrame
        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df["symbol"] = symbol
        logger.debug("🧱 DataFrame created | shape=%s", df.shape)

    except Exception as e:
        logger.exception("❌ Failed to fetch OHLCV data from Binance for %s: %s", symbol, e)
        raise

    # Publish to Kafka
    try:
        logger.debug("📤 Publishing %d records to Kafka topic 'market_data'", len(df))
        for idx, row in df.iterrows():
            msg = {
                "symbol": symbol,
                "timestamp": int(row["timestamp"].timestamp() * 1000),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row["volume"]),
            }
            publish_market_data(msg, topic="market_data")
        logger.info("✅ Successfully published %d messages to Kafka", len(df))
    except Exception as e:
        logger.exception("⚠️ Kafka publishing failed for %s: %s", symbol, e)

    # Store in TimescaleDB
    try:
        logger.debug("💾 Storing live data to TimescaleDB for %s", symbol)
        store_live_dataframe(df, source="ccxt_historical")
        logger.info("✅ Stored data in TimescaleDB for %s", symbol)
    except Exception as e:
        logger.exception("⚠️ Timescale storage failed for %s: %s", symbol, e)

    # Save snapshot to MinIO
    try:
        logger.debug("🗂️ Saving historical snapshot to MinIO for %s", symbol)
        save_historical_parquet(df, symbol)
        logger.info("✅ Historical snapshot saved for %s", symbol)
    except Exception as e:
        logger.exception("⚠️ Failed to save historical snapshot for %s: %s", symbol, e)

    duration = round(time.time() - start_time, 2)
    logger.info("🏁 Completed fetch for %s [%s] in %ss", symbol, timeframe, duration)

    return df


@retry(Exception, tries=4, delay=1, backoff=2)
def fetch_historical_kite(symbol: str, timeframe: str = "1m", limit: int = 500):
    """Fetch historical OHLCV data for NSE symbols (e.g. NIFTY50) using Zerodha Kite."""
    try:
        kite_cfg = CFG.get("kite", {})
        kite = KiteConnect(api_key=kite_cfg.get("api_key"))
        kite.set_access_token(kite_cfg.get("access_token"))

        # 🔹 find the correct instrument_token for NIFTY 50
        instruments = kite.instruments("NSE")
        instrument_token = next(
            (i["instrument_token"] for i in instruments if i["tradingsymbol"] == "NIFTY 50"),
            None,
        )
        if not instrument_token:
            raise ValueError("Instrument token for NIFTY 50 not found")

        # 🔹 timeframe → interval string
        interval_map = {"1m": "minute", "5m": "5minute", "1h": "60minute", "1d": "day"}
        interval = interval_map.get(timeframe, "minute")

        # 🔹 compute date range (max 60 days per call)
        end = pd.Timestamp.utcnow()
        start = end - pd.Timedelta(days=59)

        logger.info("📈 Fetching NIFTY 50 data from %s to %s (%s)", start, end, interval)

        data = kite.historical_data(
            instrument_token, from_date=start, to_date=end, interval=interval, continuous=False
        )

        df = pd.DataFrame(data)
        if df.empty:
            logger.warning("ℹ️ No data returned for %s", symbol)
            return df

        df.rename(columns={"date": "timestamp"}, inplace=True)
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        logger.info("✅ Fetched %d rows for %s via Kite Connect", len(df), symbol)
        return df

    except Exception as e:
        logger.exception("❌ Kite fetch failed for %s: %s", symbol, e)
        return pd.DataFrame()

