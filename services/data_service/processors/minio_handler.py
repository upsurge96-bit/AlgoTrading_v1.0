"""
MinIO Handler
Handles storage of market data to MinIO for long-term archival
"""

import os
import io
import json
import logging
import pyarrow as pa
import pyarrow.parquet as pq
from typing import List, Dict, Any, Optional
from datetime import datetime, date
from minio import Minio
from minio.error import S3Error

logger = logging.getLogger(__name__)


class MinIOHandler:
    """
    MinIO handler for storing market data
    
    Stores data in Parquet format organized by:
    - Date (YYYY/MM/DD)
    - Instrument token
    - Data type (ticks/ohlcv)
    """
    
    def __init__(
        self,
        endpoint: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        bucket: Optional[str] = None,
        secure: bool = False
    ):
        """
        Initialize MinIO handler
        
        Args:
            endpoint: MinIO endpoint
            access_key: MinIO access key
            secret_key: MinIO secret key
            bucket: Bucket name
            secure: Use HTTPS
        """
        self.endpoint = endpoint or os.getenv("MINIO_ENDPOINT", "minio:9000")
        self.access_key = access_key or os.getenv("MINIO_ACCESS_KEY", "minioaccess")
        self.secret_key = secret_key or os.getenv("MINIO_SECRET_KEY", "miniopass")
        self.bucket = bucket or os.getenv("MINIO_BUCKET", "market-data")
        self.secure = secure or os.getenv("MINIO_SECURE", "false").lower() == "true"
        
        # Initialize MinIO client
        self.client = Minio(
            self.endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=self.secure
        )
        
        # Ensure bucket exists
        self._ensure_bucket_exists()
        
        logger.info(f"MinIO handler initialized: {self.endpoint}/{self.bucket}")
    
    def _ensure_bucket_exists(self):
        """Create bucket if it doesn't exist"""
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
                logger.info(f"Created MinIO bucket: {self.bucket}")
            else:
                logger.debug(f"MinIO bucket exists: {self.bucket}")
        except S3Error as e:
            logger.error(f"Error creating bucket: {e}")
            raise
    
    def store_ticks(self, ticks: List[Dict[str, Any]]) -> str:
        """
        Store tick data to MinIO in Parquet format
        
        Args:
            ticks: List of tick data dictionaries
            
        Returns:
            Object path in MinIO
        """
        if not ticks:
            logger.warning("Empty ticks list, nothing to store")
            return ""
        
        try:
            # Group ticks by date and instrument
            grouped = self._group_ticks_by_date_and_instrument(ticks)
            
            paths = []
            for (date_str, instrument_token), tick_group in grouped.items():
                # Convert to Parquet
                parquet_buffer = self._ticks_to_parquet(tick_group)
                
                # Generate object path: ticks/YYYY/MM/DD/instrument_token_HHMMSS.parquet
                timestamp = datetime.utcnow().strftime("%H%M%S")
                object_path = f"ticks/{date_str}/{instrument_token}_{timestamp}.parquet"
                
                # Upload to MinIO
                self.client.put_object(
                    bucket_name=self.bucket,
                    object_name=object_path,
                    data=parquet_buffer,
                    length=parquet_buffer.getbuffer().nbytes,
                    content_type="application/octet-stream"
                )
                
                paths.append(object_path)
                logger.debug(f"Stored {len(tick_group)} ticks to {object_path}")
            
            logger.info(f"Stored {len(ticks)} ticks to {len(paths)} objects in MinIO")
            return ", ".join(paths)
            
        except Exception as e:
            logger.error(f"Error storing ticks to MinIO: {e}")
            raise
    
    def store_ohlcv(self, ohlcv_data: List[Dict[str, Any]]) -> str:
        """
        Store OHLCV data to MinIO in Parquet format
        
        Args:
            ohlcv_data: List of OHLCV data dictionaries
            
        Returns:
            Object path in MinIO
        """
        if not ohlcv_data:
            logger.warning("Empty OHLCV list, nothing to store")
            return ""
        
        try:
            # Group by date, instrument, and interval
            grouped = self._group_ohlcv_by_date_instrument_interval(ohlcv_data)
            
            paths = []
            for (date_str, instrument_token, interval), ohlcv_group in grouped.items():
                # Convert to Parquet
                parquet_buffer = self._ohlcv_to_parquet(ohlcv_group)
                
                # Generate object path: ohlcv/YYYY/MM/DD/interval/instrument_token.parquet
                object_path = f"ohlcv/{date_str}/{interval}/{instrument_token}.parquet"
                
                # Upload to MinIO
                self.client.put_object(
                    bucket_name=self.bucket,
                    object_name=object_path,
                    data=parquet_buffer,
                    length=parquet_buffer.getbuffer().nbytes,
                    content_type="application/octet-stream"
                )
                
                paths.append(object_path)
                logger.debug(f"Stored {len(ohlcv_group)} OHLCV records to {object_path}")
            
            logger.info(f"Stored {len(ohlcv_data)} OHLCV records to {len(paths)} objects in MinIO")
            return ", ".join(paths)
            
        except Exception as e:
            logger.error(f"Error storing OHLCV to MinIO: {e}")
            raise
    
    def _group_ticks_by_date_and_instrument(self, ticks: List[Dict[str, Any]]) -> Dict:
        """Group ticks by date and instrument token"""
        grouped = {}
        
        for tick in ticks:
            timestamp = tick.get("timestamp", datetime.utcnow())
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp)
            
            date_str = timestamp.strftime("%Y/%m/%d")
            instrument_token = tick["instrument_token"]
            
            key = (date_str, instrument_token)
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(tick)
        
        return grouped
    
    def _group_ohlcv_by_date_instrument_interval(self, ohlcv_data: List[Dict[str, Any]]) -> Dict:
        """Group OHLCV by date, instrument token, and interval"""
        grouped = {}
        
        for ohlcv in ohlcv_data:
            timestamp = ohlcv.get("timestamp", datetime.utcnow())
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp)
            
            date_str = timestamp.strftime("%Y/%m/%d")
            instrument_token = ohlcv["instrument_token"]
            interval = ohlcv["interval"]
            
            key = (date_str, instrument_token, interval)
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(ohlcv)
        
        return grouped
    
    def _ticks_to_parquet(self, ticks: List[Dict[str, Any]]) -> io.BytesIO:
        """Convert ticks to Parquet format"""
        # Prepare data for PyArrow
        data = {
            "timestamp": [],
            "instrument_token": [],
            "last_price": [],
            "last_quantity": [],
            "average_price": [],
            "volume": [],
            "buy_quantity": [],
            "sell_quantity": [],
            "open": [],
            "high": [],
            "low": [],
            "close": [],
            "oi": [],
            "mode": []
        }
        
        for tick in ticks:
            timestamp = tick.get("timestamp", datetime.utcnow())
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp)
            
            data["timestamp"].append(timestamp)
            data["instrument_token"].append(tick["instrument_token"])
            data["last_price"].append(tick.get("last_price"))
            data["last_quantity"].append(tick.get("last_quantity"))
            data["average_price"].append(tick.get("average_price"))
            data["volume"].append(tick.get("volume"))
            data["buy_quantity"].append(tick.get("buy_quantity"))
            data["sell_quantity"].append(tick.get("sell_quantity"))
            data["open"].append(tick.get("open"))
            data["high"].append(tick.get("high"))
            data["low"].append(tick.get("low"))
            data["close"].append(tick.get("close"))
            data["oi"].append(tick.get("oi"))
            data["mode"].append(tick.get("mode", "quote"))
        
        # Create PyArrow table
        table = pa.table(data)
        
        # Write to Parquet
        buffer = io.BytesIO()
        pq.write_table(table, buffer, compression='snappy')
        buffer.seek(0)
        
        return buffer
    
    def _ohlcv_to_parquet(self, ohlcv_data: List[Dict[str, Any]]) -> io.BytesIO:
        """Convert OHLCV to Parquet format"""
        # Prepare data for PyArrow
        data = {
            "timestamp": [],
            "instrument_token": [],
            "interval": [],
            "open": [],
            "high": [],
            "low": [],
            "close": [],
            "volume": [],
            "oi": [],
            "trades": []
        }
        
        for ohlcv in ohlcv_data:
            timestamp = ohlcv.get("timestamp", datetime.utcnow())
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp)
            
            data["timestamp"].append(timestamp)
            data["instrument_token"].append(ohlcv["instrument_token"])
            data["interval"].append(ohlcv["interval"])
            data["open"].append(float(ohlcv["open"]))
            data["high"].append(float(ohlcv["high"]))
            data["low"].append(float(ohlcv["low"]))
            data["close"].append(float(ohlcv["close"]))
            data["volume"].append(int(ohlcv["volume"]))
            data["oi"].append(ohlcv.get("oi"))
            data["trades"].append(ohlcv.get("trades"))
        
        # Create PyArrow table
        table = pa.table(data)
        
        # Write to Parquet
        buffer = io.BytesIO()
        pq.write_table(table, buffer, compression='snappy')
        buffer.seek(0)
        
        return buffer
    
    def read_ticks(self, date: date, instrument_token: int) -> List[Dict[str, Any]]:
        """
        Read tick data from MinIO
        
        Args:
            date: Date to read
            instrument_token: Instrument token
            
        Returns:
            List of tick data dictionaries
        """
        try:
            date_str = date.strftime("%Y/%m/%d")
            prefix = f"ticks/{date_str}/{instrument_token}_"
            
            # List objects
            objects = self.client.list_objects(self.bucket, prefix=prefix)
            
            all_ticks = []
            for obj in objects:
                # Read object
                response = self.client.get_object(self.bucket, obj.object_name)
                data = response.read()
                response.close()
                
                # Parse Parquet
                buffer = io.BytesIO(data)
                table = pq.read_table(buffer)
                df = table.to_pandas()
                
                # Convert to dict
                ticks = df.to_dict('records')
                all_ticks.extend(ticks)
            
            return all_ticks
            
        except Exception as e:
            logger.error(f"Error reading ticks from MinIO: {e}")
            return []
    
    def read_ohlcv(
        self, 
        date: date, 
        instrument_token: int, 
        interval: str
    ) -> List[Dict[str, Any]]:
        """
        Read OHLCV data from MinIO
        
        Args:
            date: Date to read
            instrument_token: Instrument token
            interval: Interval (1m, 5m, 1d, etc.)
            
        Returns:
            List of OHLCV data dictionaries
        """
        try:
            date_str = date.strftime("%Y/%m/%d")
            object_path = f"ohlcv/{date_str}/{interval}/{instrument_token}.parquet"
            
            # Read object
            response = self.client.get_object(self.bucket, object_path)
            data = response.read()
            response.close()
            
            # Parse Parquet
            buffer = io.BytesIO(data)
            table = pq.read_table(buffer)
            df = table.to_pandas()
            
            # Convert to dict
            ohlcv_data = df.to_dict('records')
            
            return ohlcv_data
            
        except S3Error as e:
            if e.code == 'NoSuchKey':
                logger.warning(f"Object not found: {object_path}")
                return []
            else:
                logger.error(f"Error reading OHLCV from MinIO: {e}")
                return []
        except Exception as e:
            logger.error(f"Error reading OHLCV from MinIO: {e}")
            return []
