"""
Historical Data Loader - Daily Scheduled Job
Fetches historical market data from Kite API and stores to MinIO

Features:
- Scheduled to run daily at 4:30 PM IST
- Configurable symbols and intervals
- Partitioned storage: Symbol/Year/Month/Week/Day/Hour
- Incremental loading - only fetches new data
- Comprehensive logging
"""

import os
import sys
import logging
from datetime import datetime, timedelta, time as dt_time
from typing import List, Dict, Any, Optional
from pathlib import Path
from zoneinfo import ZoneInfo
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from io import BytesIO

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from core.utils.logger import setup_logging, get_logger
from core.utils.time_utils import utc_now, format_iso
from services.data_service.extraction.auth_client import AuthClient
from services.data_service.processors.minio_handler import MinIOHandler
from minio import Minio
from minio.error import S3Error
import requests

# Setup logging
setup_logging(
    service_name="historical_data_loader",
    log_level=os.getenv("LOG_LEVEL", "INFO")
)
logger = get_logger(__name__)

# Timezone
IST = ZoneInfo("Asia/Kolkata")


class HistoricalDataLoader:
    """
    Daily historical data loader with MinIO storage
    
    Configuration via environment variables:
    - HISTORICAL_SYMBOLS: Comma-separated list of instrument tokens (default: config)
    - HISTORICAL_INTERVALS: Comma-separated intervals (default: 1m,5m,15m,1h,1d)
    - HISTORICAL_SCHEDULE_TIME: Time to run daily in IST (default: 16:30)
    - MINIO_ENDPOINT: MinIO endpoint
    - MINIO_ACCESS_KEY: MinIO access key
    - MINIO_SECRET_KEY: MinIO secret key
    - MINIO_BUCKET: MinIO bucket name (default: market-data)
    """
    
    def __init__(
        self,
        symbols: Optional[List[int]] = None,
        intervals: Optional[List[str]] = None,
        schedule_time: str = "16:30"
    ):
        """
        Initialize Historical Data Loader
        
        Args:
            symbols: List of instrument tokens (if None, loads from env/config)
            intervals: List of intervals (if None, loads from env)
            schedule_time: Time to run daily in HH:MM format (IST)
        """
        # Load configuration
        self.symbols = symbols or self._load_symbols_from_config()
        self.intervals = intervals or self._load_intervals_from_config()
        self.schedule_time = self._parse_schedule_time(schedule_time)
        
        # Initialize clients
        self.auth_client = AuthClient()
        self.minio_client = self._initialize_minio()
        self.bucket = os.getenv("MINIO_BUCKET", "market-data")
        
        # Ensure bucket exists
        self._ensure_bucket_exists()
        
        # Get symbol name mapping
        self.symbol_mapping = self._load_symbol_mapping()
        
        logger.info(f"✅ HistoricalDataLoader initialized")
        logger.info(f"   Symbols: {len(self.symbols)} instruments")
        logger.info(f"   Intervals: {', '.join(self.intervals)}")
        logger.info(f"   Schedule: Daily at {schedule_time} IST")
        logger.info(f"   MinIO Bucket: {self.bucket}")
    
    def _load_symbols_from_config(self) -> List[int]:
        """Load instrument tokens from environment or config"""
        # Try environment variable first
        env_symbols = os.getenv("HISTORICAL_SYMBOLS", "")
        if env_symbols:
            tokens = [int(t.strip()) for t in env_symbols.split(",") if t.strip()]
            logger.info(f"Loaded {len(tokens)} symbols from HISTORICAL_SYMBOLS env")
            return tokens
        
        # Try loading from config
        try:
            from services.data_service.config import get_settings
            settings = get_settings()
            tokens = settings.instruments.tokens
            logger.info(f"Loaded {len(tokens)} symbols from config")
            return tokens
        except Exception as e:
            logger.warning(f"Could not load symbols from config: {e}")
            # Default symbols
            default = [408065, 884737, 738561]  # NIFTY 50, BANKNIFTY, INFY
            logger.info(f"Using default symbols: {default}")
            return default
    
    def _load_intervals_from_config(self) -> List[str]:
        """Load intervals from environment"""
        env_intervals = os.getenv("HISTORICAL_INTERVALS", "minute,5minute,15minute,60minute,day")
        intervals = [i.strip() for i in env_intervals.split(",") if i.strip()]
        logger.info(f"Loaded intervals: {', '.join(intervals)}")
        return intervals
    
    def _parse_schedule_time(self, schedule_time: str) -> dt_time:
        """Parse schedule time string to time object"""
        try:
            hour, minute = map(int, schedule_time.split(":"))
            return dt_time(hour=hour, minute=minute)
        except Exception as e:
            logger.warning(f"Invalid schedule time '{schedule_time}', using default 16:30")
            return dt_time(hour=16, minute=30)
    
    def _initialize_minio(self) -> Minio:
        """Initialize MinIO client"""
        endpoint = os.getenv("MINIO_ENDPOINT", "minio:9000")
        access_key = os.getenv("MINIO_ACCESS_KEY", "minioaccess")
        secret_key = os.getenv("MINIO_SECRET_KEY", "miniopass")
        secure = os.getenv("MINIO_SECURE", "false").lower() == "true"
        
        client = Minio(
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure
        )
        
        logger.info(f"MinIO client initialized: {endpoint}")
        return client
    
    def _ensure_bucket_exists(self):
        """Ensure MinIO bucket exists"""
        try:
            if not self.minio_client.bucket_exists(self.bucket):
                self.minio_client.make_bucket(self.bucket)
                logger.info(f"✅ Created MinIO bucket: {self.bucket}")
            else:
                logger.debug(f"MinIO bucket exists: {self.bucket}")
        except S3Error as e:
            logger.error(f"❌ Error with MinIO bucket: {e}")
            raise
    
    def _load_symbol_mapping(self) -> Dict[int, str]:
        """
        Load instrument token to symbol name mapping
        
        Returns:
            Dict mapping instrument_token -> trading_symbol
        """
        # Try to load from database
        try:
            from core.db.session import get_db_session
            from services.data_service.db.models import InstrumentMaster
            
            with get_db_session() as session:
                instruments = session.query(InstrumentMaster).all()
                mapping = {inst.instrument_token: inst.tradingsymbol for inst in instruments}
                logger.info(f"Loaded {len(mapping)} symbol mappings from database")
                return mapping
        except Exception as e:
            logger.warning(f"Could not load symbol mapping from database: {e}")
        
        # Fallback to hardcoded mapping (common symbols)
        fallback = {
            408065: "NIFTY50",
            884737: "BANKNIFTY",
            738561: "INFY",
            779521: "TCS",
            340481: "RELIANCE",
            256265: "SBIN",
            264969: "HDFCBANK"
        }
        logger.info(f"Using fallback symbol mapping with {len(fallback)} symbols")
        return fallback
    
    def get_symbol_name(self, instrument_token: int) -> str:
        """Get symbol name for instrument token"""
        return self.symbol_mapping.get(instrument_token, f"TOKEN_{instrument_token}")
    
    def generate_minio_path(
        self,
        symbol_name: str,
        timestamp: datetime,
        interval: str
    ) -> str:
        """
        Generate MinIO object path with partitioning
        
        Path format: historical/{symbol}/{year}/{month}/{week}/{day}/{hour}/{interval}.parquet
        
        Args:
            symbol_name: Trading symbol name
            timestamp: Data timestamp
            interval: Data interval (1m, 5m, etc.)
            
        Returns:
            Object path string
        """
        # Ensure timestamp is timezone-aware
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=IST)
        
        # Convert to IST for partitioning
        ist_time = timestamp.astimezone(IST)
        
        # Extract partition components
        year = ist_time.strftime("%Y")
        month = ist_time.strftime("%m")
        week = ist_time.strftime("%U")  # Week number (00-53)
        day = ist_time.strftime("%d")
        hour = ist_time.strftime("%H")
        
        # Normalize interval name
        interval_normalized = self._normalize_interval(interval)
        
        # Construct path
        path = f"historical/{symbol_name}/{year}/{month}/{week}/{day}/{hour}/{interval_normalized}.parquet"
        
        return path
    
    def _normalize_interval(self, interval: str) -> str:
        """Normalize interval to standard format"""
        mapping = {
            "minute": "1m",
            "3minute": "3m",
            "5minute": "5m",
            "10minute": "10m",
            "15minute": "15m",
            "30minute": "30m",
            "60minute": "1h",
            "day": "1d"
        }
        return mapping.get(interval, interval)
    
    def check_existing_data(
        self,
        symbol_name: str,
        date: datetime,
        interval: str
    ) -> bool:
        """
        Check if data already exists in MinIO for given symbol/date/interval
        
        Args:
            symbol_name: Trading symbol
            date: Date to check
            interval: Interval to check
            
        Returns:
            True if data exists, False otherwise
        """
        path = self.generate_minio_path(symbol_name, date, interval)
        
        try:
            self.minio_client.stat_object(self.bucket, path)
            logger.debug(f"Data exists: {path}")
            return True
        except S3Error as e:
            if e.code == 'NoSuchKey':
                logger.debug(f"Data not found: {path}")
                return False
            else:
                logger.error(f"Error checking MinIO object: {e}")
                return False
    
    def fetch_historical_data(
        self,
        instrument_token: int,
        interval: str,
        from_date: datetime,
        to_date: datetime
    ) -> Optional[pd.DataFrame]:
        """
        Fetch historical data from Kite API
        
        Args:
            instrument_token: Instrument token
            interval: Interval (minute, 5minute, etc.)
            from_date: Start date
            to_date: End date
            
        Returns:
            DataFrame with OHLCV data or None if failed
        """
        try:
            # Get access token
            access_token = self.auth_client.get_access_token()
            if not access_token:
                logger.error("Failed to get access token")
                return None
            
            api_key = self.auth_client.get_api_key()
            
            # Format dates
            from_str = from_date.strftime("%Y-%m-%d %H:%M:%S")
            to_str = to_date.strftime("%Y-%m-%d %H:%M:%S")
            
            # API URL
            url = f"https://api.kite.trade/instruments/historical/{instrument_token}/{interval}"
            
            headers = {
                "X-Kite-Version": "3",
                "Authorization": f"token {api_key}:{access_token}"
            }
            
            params = {
                "from": from_str,
                "to": to_str,
                "oi": 1  # Include open interest
            }
            
            logger.debug(f"Fetching: {url} from={from_str} to={to_str}")
            
            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get("status") != "success":
                logger.error(f"API error: {data}")
                return None
            
            candles = data.get("data", {}).get("candles", [])
            
            if not candles:
                logger.info(f"No data returned for token={instrument_token}, interval={interval}")
                return None
            
            # Create DataFrame
            columns = ["timestamp", "open", "high", "low", "close", "volume", "oi"]
            df = pd.DataFrame(candles, columns=columns)
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            
            logger.info(f"✅ Fetched {len(df)} candles for token={instrument_token}, interval={interval}")
            
            return df
            
        except Exception as e:
            logger.error(f"❌ Error fetching data: {e}")
            return None
    
    def store_to_minio(
        self,
        df: pd.DataFrame,
        symbol_name: str,
        interval: str
    ) -> bool:
        """
        Store DataFrame to MinIO in Parquet format with partitioning
        
        Args:
            df: DataFrame with OHLCV data
            symbol_name: Trading symbol name
            interval: Data interval
            
        Returns:
            True if successful, False otherwise
        """
        if df.empty:
            logger.warning("Empty DataFrame, nothing to store")
            return False
        
        try:
            # Group by date and hour for partitioning
            df['date'] = df['timestamp'].dt.date
            df['hour'] = df['timestamp'].dt.hour
            
            grouped = df.groupby(['date', 'hour'])
            
            stored_count = 0
            
            for (date, hour), group in grouped:
                # Create timestamp for partitioning
                partition_ts = datetime.combine(date, dt_time(hour=hour))
                partition_ts = partition_ts.replace(tzinfo=IST)
                
                # Generate MinIO path
                path = self.generate_minio_path(symbol_name, partition_ts, interval)
                
                # Convert to Parquet
                table = pa.Table.from_pandas(
                    group[['timestamp', 'open', 'high', 'low', 'close', 'volume', 'oi']],
                    preserve_index=False
                )
                
                # Write to buffer
                buffer = BytesIO()
                pq.write_table(table, buffer, compression='snappy')
                buffer.seek(0)
                
                # Upload to MinIO
                self.minio_client.put_object(
                    bucket_name=self.bucket,
                    object_name=path,
                    data=buffer,
                    length=buffer.getbuffer().nbytes,
                    content_type="application/octet-stream"
                )
                
                logger.debug(f"Stored {len(group)} records to {path}")
                stored_count += 1
            
            logger.info(f"✅ Stored {len(df)} records across {stored_count} partitions to MinIO")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error storing to MinIO: {e}")
            return False
    
    def load_daily_data(self, target_date: Optional[datetime] = None):
        """
        Load data for a specific day (default: previous trading day)
        
        Args:
            target_date: Date to load (if None, uses previous day)
        """
        # Determine target date
        if target_date is None:
            # Use previous day
            now_ist = datetime.now(IST)
            target_date = (now_ist - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        
        logger.info(f"=" * 70)
        logger.info(f"📅 Loading historical data for: {target_date.date()}")
        logger.info(f"=" * 70)
        
        # Define trading hours (IST)
        market_open = target_date.replace(hour=9, minute=15)
        market_close = target_date.replace(hour=15, minute=30)
        
        total_tasks = len(self.symbols) * len(self.intervals)
        completed = 0
        skipped = 0
        failed = 0
        start_time = utc_now()
        
        logger.info(f"💓 Starting data load: {total_tasks} tasks total")
        
        for instrument_token in self.symbols:
            symbol_name = self.get_symbol_name(instrument_token)
            
            for interval in self.intervals:
                completed += 1
                
                # Heartbeat logging - progress update
                progress_pct = (completed / total_tasks) * 100
                elapsed = (utc_now() - start_time).total_seconds()
                avg_time = elapsed / completed if completed > 0 else 0
                eta_seconds = avg_time * (total_tasks - completed)
                eta_minutes = int(eta_seconds / 60)
                
                logger.info(f"💓 PROGRESS | "
                          f"Task {completed}/{total_tasks} ({progress_pct:.1f}%) | "
                          f"Symbol: {symbol_name} | "
                          f"Interval: {interval} | "
                          f"Elapsed: {int(elapsed/60)}m | "
                          f"ETA: {eta_minutes}m")
                
                logger.info(f"[{completed}/{total_tasks}] Processing: {symbol_name} ({instrument_token}) - {interval}")
                
                # Check if data already exists
                if self.check_existing_data(symbol_name, target_date, interval):
                    logger.info(f"⏭️  Data already exists, skipping")
                    skipped += 1
                    continue
                
                # Fetch data
                df = self.fetch_historical_data(
                    instrument_token=instrument_token,
                    interval=interval,
                    from_date=market_open,
                    to_date=market_close
                )
                
                if df is None or df.empty:
                    logger.warning(f"⚠️  No data fetched")
                    failed += 1
                    continue
                
                # Store to MinIO
                success = self.store_to_minio(df, symbol_name, interval)
                
                if not success:
                    failed += 1
                
                # Rate limiting
                import time
                time.sleep(0.5)
        
        # Summary
        end_time = utc_now()
        total_duration = (end_time - start_time).total_seconds()
        duration_minutes = int(total_duration / 60)
        duration_seconds = int(total_duration % 60)
        
        logger.info(f"=" * 70)
        logger.info(f"� FINAL HEARTBEAT - Load Complete")
        logger.info(f"=" * 70)
        logger.info(f"�📊 Daily Load Summary for {target_date.date()}")
        logger.info(f"   Total Tasks: {total_tasks}")
        logger.info(f"   ✅ Completed: {completed - skipped - failed}")
        logger.info(f"   ⏭️  Skipped (existing): {skipped}")
        logger.info(f"   ❌ Failed: {failed}")
        logger.info(f"   ⏱️  Duration: {duration_minutes}m {duration_seconds}s")
        logger.info(f"   📈 Success Rate: {((completed - skipped - failed) / total_tasks * 100):.1f}%")
        logger.info(f"=" * 70)
        logger.info(f"   ❌ Failed: {failed}")
        logger.info(f"=" * 70)
    
    def run_scheduled_job(self):
        """
        Run the scheduled daily job
        
        This should be called by the scheduler at the configured time
        """
        logger.info(f"🕐 Scheduled job triggered at {datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')} IST")
        
        try:
            self.load_daily_data()
        except Exception as e:
            logger.error(f"❌ Scheduled job failed: {e}", exc_info=True)


def main():
    """Main entry point for testing"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Historical Data Loader")
    parser.add_argument("--date", help="Date to load (YYYY-MM-DD)", default=None)
    parser.add_argument("--symbols", help="Comma-separated instrument tokens", default=None)
    parser.add_argument("--intervals", help="Comma-separated intervals", default=None)
    
    args = parser.parse_args()
    
    # Parse symbols
    symbols = None
    if args.symbols:
        symbols = [int(t.strip()) for t in args.symbols.split(",")]
    
    # Parse intervals
    intervals = None
    if args.intervals:
        intervals = [i.strip() for i in args.intervals.split(",")]
    
    # Parse date
    target_date = None
    if args.date:
        target_date = datetime.strptime(args.date, "%Y-%m-%d").replace(tzinfo=IST)
    
    # Create loader
    loader = HistoricalDataLoader(symbols=symbols, intervals=intervals)
    
    # Run
    loader.load_daily_data(target_date=target_date)


if __name__ == "__main__":
    main()
