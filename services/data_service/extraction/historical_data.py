"""
Historical Data Fetcher
Fetches historical candle data from Kite API and stores to MinIO
"""

import requests
import pandas as pd
from datetime import datetime, timedelta
import sys
import logging
from typing import List, Dict, Any, Optional
from services.data_service.extraction.auth_client import AuthClient
from services.data_service.processors.minio_handler import MinIOHandler
from services.data_service.processors.tick_processor import OHLCVProcessor

logger = logging.getLogger(__name__)


class HistoricalDataFetcher:
    """
    Fetch historical candle data from Kite API
    
    Features:
    - Fetch data for multiple instruments
    - Multiple timeframes (1m, 5m, 15m, 1h, 1d)
    - Automatic chunking for large date ranges
    - Store to MinIO for long-term archival
    - Store to TimescaleDB for querying
    """
    
    def __init__(
        self,
        auth_client: Optional[AuthClient] = None,
        minio_handler: Optional[MinIOHandler] = None,
        ohlcv_processor: Optional[OHLCVProcessor] = None,
        max_days_per_request: int = 60
    ):
        """
        Initialize Historical Data Fetcher
        
        Args:
            auth_client: Auth client for tokens
            minio_handler: MinIO handler for storage
            ohlcv_processor: OHLCV processor for database storage
            max_days_per_request: Maximum days per API request (to avoid rate limits)
        """
        self.auth_client = auth_client or AuthClient()
        self.minio_handler = minio_handler or MinIOHandler()
        self.ohlcv_processor = ohlcv_processor or OHLCVProcessor()
        self.max_days_per_request = max_days_per_request
        
        self.api_key = self.auth_client.get_api_key()
        self.access_token = None
        
        logger.info("HistoricalDataFetcher initialized")
    
    def _get_access_token(self) -> str:
        """Get access token from auth client"""
        if not self.access_token:
            self.access_token = self.auth_client.get_access_token()
            if not self.access_token:
                raise RuntimeError("Failed to get access token")
        return self.access_token
    
    def fetch_historical_data(
        self,
        instrument_token: int,
        interval: str,
        from_date: datetime,
        to_date: datetime,
        continuous: int = 0,
        oi: int = 0,
        timeout: int = 30,
        max_retries: int = 3
    ) -> pd.DataFrame:
        """
        Fetch historical candle data from Kite API
        
        Args:
            instrument_token: Instrument token
            interval: Interval ('minute', '5minute', '15minute', '30minute', '60minute', 'day')
            from_date: Start date
            to_date: End date
            continuous: 1 for continuous futures data
            oi: 1 to include open interest data
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries
            
        Returns:
            DataFrame of historical candles
        """
        # Format dates
        if isinstance(from_date, datetime):
            from_date_str = from_date.strftime("%Y-%m-%d %H:%M:%S")
        else:
            from_date_str = from_date
            
        if isinstance(to_date, datetime):
            to_date_str = to_date.strftime("%Y-%m-%d %H:%M:%S")
        else:
            to_date_str = to_date
        
        # Get access token
        access_token = self._get_access_token()
        
        url = f"https://api.kite.trade/instruments/historical/{instrument_token}/{interval}"
        headers = {
            "X-Kite-Version": "3",
            "Authorization": f"token {self.api_key}:{access_token}"
        }
        
        params = {
            "from": from_date_str,
            "to": to_date_str,
            "continuous": continuous,
            "oi": oi
        }
        
        # Use session with retries
        session = requests.Session()
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        
        retries = Retry(
            total=max_retries,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504]
        )
        session.mount("https://", HTTPAdapter(max_retries=retries))
        
        try:
            logger.info(f"Fetching historical data: token={instrument_token}, interval={interval}, from={from_date_str}, to={to_date_str}")
            response = session.get(url, headers=headers, params=params, timeout=timeout)
            response.raise_for_status()
            
        except requests.RequestException as e:
            logger.error(f"Network error while fetching historical data: {e}")
            raise RuntimeError(f"Network error: {e}")
        
        if response.status_code != 200:
            logger.error(f"HTTP {response.status_code}: {response.text}")
            raise RuntimeError(f"HTTP {response.status_code}: {response.text}")
        
        data = response.json()
        
        if data.get("status") != "success":
            logger.error(f"API call failed: {data}")
            raise RuntimeError(f"API call failed: {data}")
        
        candles = data.get("data", {}).get("candles", [])
        
        if not candles:
            logger.warning("No data returned for the given range")
            return pd.DataFrame()
        
        # Define columns based on whether OI is included
        columns = ["timestamp", "open", "high", "low", "close", "volume"]
        if oi:
            columns.append("oi")
        
        df = pd.DataFrame(candles, columns=columns)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        
        logger.info(f"Fetched {len(df)} candles")
        return df
    
    def fetch_and_store_historical_data(
        self,
        instrument_token: int,
        interval: str,
        from_date: datetime,
        to_date: datetime,
        continuous: int = 0,
        oi: int = 1
    ):
        """
        Fetch historical data and store to both MinIO and TimescaleDB
        
        Automatically chunks large date ranges to avoid API limits
        
        Args:
            instrument_token: Instrument token
            interval: Interval
            from_date: Start date
            to_date: End date
            continuous: 1 for continuous futures data
            oi: 1 to include OI data
        """
        # Calculate date chunks
        date_chunks = self._get_date_chunks(from_date, to_date)
        
        all_data = []
        
        for chunk_start, chunk_end in date_chunks:
            try:
                # Fetch data for this chunk
                df = self.fetch_historical_data(
                    instrument_token=instrument_token,
                    interval=interval,
                    from_date=chunk_start,
                    to_date=chunk_end,
                    continuous=continuous,
                    oi=oi
                )
                
                if not df.empty:
                    # Convert to dict format
                    records = df.to_dict('records')
                    
                    # Add metadata
                    for record in records:
                        record['instrument_token'] = instrument_token
                        record['interval'] = self._normalize_interval(interval)
                    
                    all_data.extend(records)
                    
                # Rate limiting - sleep between requests
                import time
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Error fetching chunk {chunk_start} to {chunk_end}: {e}")
                # Continue with next chunk
        
        if all_data:
            logger.info(f"Fetched total {len(all_data)} candles")
            
            # Store to MinIO
            try:
                self.minio_handler.store_ohlcv(all_data)
                logger.info("Stored historical data to MinIO")
            except Exception as e:
                logger.error(f"Error storing to MinIO: {e}")
            
            # Store to TimescaleDB
            try:
                self.ohlcv_processor.process_batch(all_data)
                logger.info("Stored historical data to TimescaleDB")
            except Exception as e:
                logger.error(f"Error storing to TimescaleDB: {e}")
        else:
            logger.warning("No historical data fetched")
    
    def fetch_5_years_data(
        self,
        instrument_tokens: List[int],
        intervals: List[str] = ["day", "60minute", "15minute"],
        oi: int = 1
    ):
        """
        Fetch 5 years of historical data for given instruments
        
        Args:
            instrument_tokens: List of instrument tokens
            intervals: List of intervals to fetch
            oi: Include OI data
        """
        # Calculate date range (5 years)
        to_date = datetime.now()
        from_date = to_date - timedelta(days=5*365)
        
        logger.info(f"Fetching 5 years data from {from_date} to {to_date}")
        logger.info(f"Instruments: {len(instrument_tokens)}, Intervals: {intervals}")
        
        total = len(instrument_tokens) * len(intervals)
        current = 0
        
        for instrument_token in instrument_tokens:
            for interval in intervals:
                current += 1
                logger.info(f"Progress: {current}/{total} - Token: {instrument_token}, Interval: {interval}")
                
                try:
                    self.fetch_and_store_historical_data(
                        instrument_token=instrument_token,
                        interval=interval,
                        from_date=from_date,
                        to_date=to_date,
                        oi=oi
                    )
                except Exception as e:
                    logger.error(f"Error fetching data for {instrument_token} {interval}: {e}")
                    # Continue with next
        
        logger.info(f"Completed fetching 5 years data for {len(instrument_tokens)} instruments")
    
    def fetch_incremental_data(
        self,
        instrument_tokens: List[int],
        intervals: List[str] = ["day", "60minute", "15minute"],
        days: int = 1,
        oi: int = 1
    ):
        """
        Fetch incremental data (e.g., daily update)
        
        Args:
            instrument_tokens: List of instrument tokens
            intervals: List of intervals to fetch
            days: Number of days to fetch
            oi: Include OI data
        """
        to_date = datetime.now()
        from_date = to_date - timedelta(days=days)
        
        logger.info(f"Fetching incremental data from {from_date} to {to_date}")
        
        for instrument_token in instrument_tokens:
            for interval in intervals:
                try:
                    self.fetch_and_store_historical_data(
                        instrument_token=instrument_token,
                        interval=interval,
                        from_date=from_date,
                        to_date=to_date,
                        oi=oi
                    )
                except Exception as e:
                    logger.error(f"Error fetching incremental data for {instrument_token} {interval}: {e}")
        
        logger.info("Completed incremental data fetch")
    
    def _get_date_chunks(
        self,
        from_date: datetime,
        to_date: datetime
    ) -> List[tuple]:
        """
        Split date range into chunks to avoid API limits
        
        Returns:
            List of (start, end) tuples
        """
        chunks = []
        current_start = from_date
        
        while current_start < to_date:
            current_end = min(
                current_start + timedelta(days=self.max_days_per_request),
                to_date
            )
            chunks.append((current_start, current_end))
            current_start = current_end
        
        return chunks
    
    def _normalize_interval(self, interval: str) -> str:
        """
        Normalize interval to standard format
        
        Args:
            interval: Kite API interval
            
        Returns:
            Normalized interval
        """
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


def get_historical_data(
    api_key: str,
    access_token: str,
    instrument_token: int,
    interval: str,
    from_date: str,
    to_date: str,
    continuous: int = 0,
    oi: int = 0,
    timeout: int = 10,
    max_retries: int = 3
) -> pd.DataFrame:
    """
    Legacy function for backward compatibility
    
    Fetch historical candle data from Kite API
    """
    # Create a temporary auth client
    class TempAuthClient:
        def __init__(self, api_key, access_token):
            self.api_key_val = api_key
            self.access_token_val = access_token
        
        def get_api_key(self):
            return self.api_key_val
        
        def get_access_token(self):
            return self.access_token_val
    
    auth_client = TempAuthClient(api_key, access_token)
    fetcher = HistoricalDataFetcher(auth_client=auth_client)
    
    return fetcher.fetch_historical_data(
        instrument_token=instrument_token,
        interval=interval,
        from_date=datetime.strptime(from_date, "%Y-%m-%d %H:%M:%S"),
        to_date=datetime.strptime(to_date, "%Y-%m-%d %H:%M:%S"),
        continuous=continuous,
        oi=oi,
        timeout=timeout,
        max_retries=max_retries
    )

if __name__ == "__main__":
	# configure logging only when running this module directly
	logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

	# Example usage (replace placeholders with your credentials)
	# Avoid embedding secrets in the file; use environment variables or a secrets manager.
	api_key = "<YOUR_API_KEY>"
	access_token = "<YOUR_ACCESS_TOKEN>"
	instrument_token = 5633  # NSE-ACC example
	interval = "minute"
	from_date = "2017-12-15 09:15:00"
	to_date = "2017-12-15 09:20:00"

	try:
		df = get_historical_data(api_key, access_token, instrument_token, interval, from_date, to_date, continuous=0, oi=0)
		if not df.empty:
			output_file = f"historical_data_{instrument_token}_{interval}.csv"
			df.to_csv(output_file, index=False)
			logger.info("Data saved to %s", output_file)
			logger.info("\n%s", df.head().to_string())
		else:
			logger.warning("No data returned for the given range.")
	except Exception as e:
		logger.exception("Error fetching historical data: %s", e)
