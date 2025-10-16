from kiteconnect import KiteConnect
from datetime import datetime, timedelta
import pandas as pd
import os
import time
from pathlib import Path

# Internal services (your existing project modules)
from services.data_service.ingestion.storage import store_live_dataframe, save_historical_parquet


# --------------------------
# SETUP KITE CLIENT
# --------------------------
kite = KiteConnect(api_key=os.getenv("KITE_API_KEY"))
kite.set_access_token(os.getenv("KITE_ACCESS_TOKEN"))


# --------------------------
# HISTORICAL FETCH FUNCTION
# --------------------------
def fetch_historical(symbol: str, instrument_token: int, start_date: str = "2020-01-01", interval: str = "minute"):
    """
    Fetch historical OHLC data from Kite starting from start_date till now.
    Automatically handles 60-day API limit, retries on failures, and saves data partitioned by time.
    """
    from_date = datetime.strptime(start_date, "%Y-%m-%d")
    to_date = datetime.now()

    print(f"📥 Fetching {interval} data for {symbol} from {from_date.date()} → {to_date.date()}")

    delta = timedelta(days=60)
    all_data = []
    retry_limit = 3  # Retry on API errors or rate limits

    while from_date < to_date:
        chunk_end = min(from_date + delta, to_date)
        print(f"⏳ Fetching chunk: {from_date.date()} → {chunk_end.date()}")

        for attempt in range(retry_limit):
            try:
                data = kite.historical_data(
                    instrument_token,
                    from_date,
                    chunk_end,
                    interval=interval,
                    continuous=False
                )
                break  # success
            except Exception as e:
                print(f"⚠️ Error fetching {from_date.date()} → {chunk_end.date()}: {e}")
                if attempt < retry_limit - 1:
                    wait = 2 ** attempt
                    print(f"🔁 Retrying in {wait}s...")
                    time.sleep(wait)
                else:
                    print(f"❌ Skipping this chunk after {retry_limit} failed attempts.")
                    data = []
                    break

        if data:
            all_data.extend(data)
            print(f"✅ Retrieved {len(data)} records.")
        else:
            print(f"⚠️ No data for chunk {from_date.date()} → {chunk_end.date()}")

        from_date = chunk_end  # move forward

    # --------------------------
    # DATA VALIDATION
    # --------------------------
    if not all_data:
        print(f"❌ No data fetched for {symbol}")
        return

    df = pd.DataFrame(all_data)
    if df.empty:
        print(f"⚠️ Empty dataframe for {symbol}")
        return

    df["symbol"] = symbol
    df.rename(columns={"date": "timestamp"}, inplace=True)
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    # Partition metadata
    df["year"] = df["timestamp"].dt.year
    df["month"] = df["timestamp"].dt.month
    df["week"] = df["timestamp"].dt.isocalendar().week
    df["date"] = df["timestamp"].dt.date.astype(str)
    df["hour"] = df["timestamp"].dt.hour

    # Save to database (if applicable)
    store_live_dataframe(df, source="historical_kite")

    # Save Parquet files partitioned by year/month/week/date/hour
    save_partitioned_historical(df, symbol)

    print(f"✅ Done. Stored {len(df)} total records for {symbol} from {start_date} → {to_date.date()}")


# --------------------------
# PARQUET SAVER FUNCTION
# --------------------------
def save_partitioned_historical(df: pd.DataFrame, symbol: str):
    """
    Save dataframe partitioned by year/month/week/date/hour as Parquet files locally and in MinIO/S3.
    """
    base_path = Path(f"historical/symbol={symbol}")
    for (year, month, week, date, hour), group in df.groupby(["year", "month", "week", "date", "hour"]):
        path = base_path / f"year={year}/month={month:02d}/week={week:02d}/date={date}/hour={hour:02d}"
        path.mkdir(parents=True, exist_ok=True)
        file_path = path / f"{symbol}_{date}_{hour:02d}.parquet"

        group.to_parquet(file_path, index=False)
        save_historical_parquet(group, symbol=symbol, prefix=str(path))  # Hook to MinIO/S3

    print(f"💾 Partitioned Parquet files saved for {symbol}")


# --------------------------
# MAIN EXECUTION
# --------------------------
if __name__ == "__main__":
    # Example: NIFTY50 1-minute data since 2020
    fetch_historical("NIFTY50", 256265, start_date="2020-01-01", interval="minute")
# services/data_service/ingestion# python3 fetch_historical_kite_timescale.py