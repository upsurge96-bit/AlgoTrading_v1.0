"""
Data Processors
Handles processing of tick data: storing to TimescaleDB, publishing to Kafka, batching to MinIO
"""

import os
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.messaging.kafka_client import KafkaClient
from services.data_service.db.models import TickData, OHLCVData, InstrumentMaster
from services.data_service.processors.minio_handler import MinIOHandler

logger = logging.getLogger(__name__)


class TickProcessor:
    """
    Process tick data from live stream
    
    - Store to TimescaleDB for real-time queries
    - Publish to Kafka for other services
    - Batch to MinIO for long-term storage
    """
    
    def __init__(
        self,
        database_url: Optional[str] = None,
        kafka_client: Optional[KafkaClient] = None,
        minio_handler: Optional[MinIOHandler] = None,
        batch_size: int = 1000,
        batch_interval_seconds: int = 60
    ):
        """
        Initialize TickProcessor
        
        Args:
            database_url: Database connection URL
            kafka_client: Kafka client instance
            minio_handler: MinIO handler instance
            batch_size: Number of ticks to batch before writing to MinIO
            batch_interval_seconds: Time interval to flush batch to MinIO
        """
        # Database setup
        self.database_url = database_url or os.getenv(
            "DATABASE_URL", 
            "postgresql://trader:traderpass@timescaledb:5432/trading"
        )
        self.engine = create_engine(self.database_url, pool_size=10, max_overflow=20)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        
        # Kafka setup
        self.kafka_client = kafka_client or KafkaClient(
            default_topic=os.getenv("KAFKA_TOPIC", "market_data")
        )
        
        # MinIO setup
        self.minio_handler = minio_handler or MinIOHandler()
        
        # Batching configuration
        self.batch_size = batch_size
        self.batch_interval_seconds = batch_interval_seconds
        self._tick_batch: List[Dict[str, Any]] = []
        self._last_flush_time = datetime.utcnow()
        
        # Statistics
        self.stats = {
            "ticks_processed": 0,
            "ticks_stored_db": 0,
            "ticks_published_kafka": 0,
            "ticks_batched_minio": 0,
            "errors": 0
        }
        
        logger.info("TickProcessor initialized")
    
    def process_tick(self, tick_data: Dict[str, Any]):
        """
        Process a single tick
        
        Args:
            tick_data: Tick data dictionary
        """
        try:
            self.stats["ticks_processed"] += 1
            
            # Store to database (async/background recommended for production)
            self._store_to_db(tick_data)
            
            # Publish to Kafka
            self._publish_to_kafka(tick_data)
            
            # Add to batch for MinIO
            self._add_to_batch(tick_data)
            
        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"Error processing tick: {e}")
            logger.exception(e)
    
    def _store_to_db(self, tick_data: Dict[str, Any]):
        """Store tick to TimescaleDB"""
        try:
            db: Session = self.SessionLocal()
            
            try:
                tick = TickData(
                    timestamp=tick_data.get("timestamp", datetime.utcnow()),
                    instrument_token=tick_data["instrument_token"],
                    last_price=tick_data.get("last_price"),
                    last_quantity=tick_data.get("last_quantity"),
                    average_price=tick_data.get("average_price"),
                    volume=tick_data.get("volume"),
                    buy_quantity=tick_data.get("buy_quantity"),
                    sell_quantity=tick_data.get("sell_quantity"),
                    open=tick_data.get("open"),
                    high=tick_data.get("high"),
                    low=tick_data.get("low"),
                    close=tick_data.get("close"),
                    oi=tick_data.get("oi"),
                    oi_day_high=tick_data.get("oi_day_high"),
                    oi_day_low=tick_data.get("oi_day_low"),
                    exchange_timestamp=tick_data.get("exchange_timestamp"),
                    depth=tick_data.get("depth"),
                    mode=tick_data.get("mode", "quote"),
                    tradable=True
                )
                
                db.add(tick)
                db.commit()
                self.stats["ticks_stored_db"] += 1
                
            except Exception as e:
                db.rollback()
                logger.error(f"Database error storing tick: {e}")
                raise
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error in _store_to_db: {e}")
    
    def _publish_to_kafka(self, tick_data: Dict[str, Any]):
        """Publish tick to Kafka"""
        try:
            # Prepare message
            message = {
                "type": "tick",
                "data": self._serialize_tick(tick_data),
                "timestamp": tick_data.get("timestamp", datetime.utcnow()).isoformat()
            }
            
            # Publish to Kafka
            self.kafka_client.send(
                topic=None,  # Uses default topic
                message=message,
                key=str(tick_data["instrument_token"])
            )
            
            self.stats["ticks_published_kafka"] += 1
            
        except Exception as e:
            logger.error(f"Error publishing to Kafka: {e}")
    
    def _add_to_batch(self, tick_data: Dict[str, Any]):
        """Add tick to batch for MinIO storage"""
        try:
            self._tick_batch.append(tick_data)
            
            # Check if batch should be flushed
            should_flush = False
            
            if len(self._tick_batch) >= self.batch_size:
                should_flush = True
                logger.debug(f"Batch size reached: {len(self._tick_batch)}")
            
            time_since_flush = (datetime.utcnow() - self._last_flush_time).total_seconds()
            if time_since_flush >= self.batch_interval_seconds:
                should_flush = True
                logger.debug(f"Batch interval reached: {time_since_flush}s")
            
            if should_flush:
                self._flush_batch()
                
        except Exception as e:
            logger.error(f"Error adding to batch: {e}")
    
    def _flush_batch(self):
        """Flush tick batch to MinIO"""
        if not self._tick_batch:
            return
        
        try:
            # Upload batch to MinIO
            self.minio_handler.store_ticks(self._tick_batch)
            
            self.stats["ticks_batched_minio"] += len(self._tick_batch)
            logger.info(f"Flushed {len(self._tick_batch)} ticks to MinIO")
            
            # Clear batch
            self._tick_batch = []
            self._last_flush_time = datetime.utcnow()
            
        except Exception as e:
            logger.error(f"Error flushing batch to MinIO: {e}")
            # Don't clear batch on error - will retry next flush
    
    def _serialize_tick(self, tick_data: Dict[str, Any]) -> Dict[str, Any]:
        """Serialize tick data for JSON transmission"""
        serialized = {}
        
        for key, value in tick_data.items():
            if isinstance(value, datetime):
                serialized[key] = value.isoformat()
            elif value is not None:
                serialized[key] = value
        
        return serialized
    
    def get_stats(self) -> Dict[str, Any]:
        """Get processor statistics"""
        return {
            **self.stats,
            "batch_size": len(self._tick_batch),
            "last_flush": self._last_flush_time.isoformat()
        }
    
    def close(self):
        """Cleanup resources"""
        try:
            # Flush remaining batch
            self._flush_batch()
            
            # Close Kafka
            self.kafka_client.close()
            
            # Close database
            self.engine.dispose()
            
            logger.info("TickProcessor closed successfully")
        except Exception as e:
            logger.error(f"Error closing TickProcessor: {e}")


class OHLCVProcessor:
    """
    Process OHLCV candle data from historical API or tick aggregation
    
    - Store to TimescaleDB
    - Publish to Kafka
    - Store to MinIO for long-term storage
    """
    
    def __init__(
        self,
        database_url: Optional[str] = None,
        kafka_client: Optional[KafkaClient] = None,
        minio_handler: Optional[MinIOHandler] = None
    ):
        """Initialize OHLCVProcessor"""
        # Database setup
        self.database_url = database_url or os.getenv(
            "DATABASE_URL", 
            "postgresql://trader:traderpass@timescaledb:5432/trading"
        )
        self.engine = create_engine(self.database_url, pool_size=10, max_overflow=20)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        
        # Kafka setup
        self.kafka_client = kafka_client or KafkaClient(
            default_topic=os.getenv("KAFKA_TOPIC", "market_data")
        )
        
        # MinIO setup
        self.minio_handler = minio_handler or MinIOHandler()
        
        logger.info("OHLCVProcessor initialized")
    
    def process_ohlcv(self, ohlcv_data: Dict[str, Any]):
        """
        Process OHLCV candle data
        
        Args:
            ohlcv_data: OHLCV data dictionary
        """
        try:
            # Store to database
            self._store_to_db(ohlcv_data)
            
            # Publish to Kafka
            self._publish_to_kafka(ohlcv_data)
            
        except Exception as e:
            logger.error(f"Error processing OHLCV: {e}")
            logger.exception(e)
    
    def process_batch(self, ohlcv_batch: List[Dict[str, Any]]):
        """
        Process batch of OHLCV data (for historical data)
        
        Args:
            ohlcv_batch: List of OHLCV data dictionaries
        """
        try:
            # Bulk insert to database
            self._bulk_store_to_db(ohlcv_batch)
            
            # Store to MinIO
            self.minio_handler.store_ohlcv(ohlcv_batch)
            
        except Exception as e:
            logger.error(f"Error processing OHLCV batch: {e}")
            logger.exception(e)
    
    def _store_to_db(self, ohlcv_data: Dict[str, Any]):
        """Store single OHLCV to TimescaleDB"""
        db: Session = self.SessionLocal()
        
        try:
            candle = OHLCVData(
                timestamp=ohlcv_data["timestamp"],
                instrument_token=ohlcv_data["instrument_token"],
                interval=ohlcv_data["interval"],
                open=ohlcv_data["open"],
                high=ohlcv_data["high"],
                low=ohlcv_data["low"],
                close=ohlcv_data["close"],
                volume=ohlcv_data["volume"],
                oi=ohlcv_data.get("oi"),
                trades=ohlcv_data.get("trades")
            )
            
            db.add(candle)
            db.commit()
            
        except Exception as e:
            db.rollback()
            logger.error(f"Database error storing OHLCV: {e}")
            raise
        finally:
            db.close()
    
    def _bulk_store_to_db(self, ohlcv_batch: List[Dict[str, Any]]):
        """Bulk insert OHLCV data to TimescaleDB"""
        db: Session = self.SessionLocal()
        
        try:
            candles = [
                OHLCVData(
                    timestamp=data["timestamp"],
                    instrument_token=data["instrument_token"],
                    interval=data["interval"],
                    open=data["open"],
                    high=data["high"],
                    low=data["low"],
                    close=data["close"],
                    volume=data["volume"],
                    oi=data.get("oi"),
                    trades=data.get("trades")
                )
                for data in ohlcv_batch
            ]
            
            db.bulk_save_objects(candles)
            db.commit()
            logger.info(f"Bulk inserted {len(candles)} OHLCV records")
            
        except Exception as e:
            db.rollback()
            logger.error(f"Database error bulk storing OHLCV: {e}")
            raise
        finally:
            db.close()
    
    def _publish_to_kafka(self, ohlcv_data: Dict[str, Any]):
        """Publish OHLCV to Kafka"""
        try:
            message = {
                "type": "ohlcv",
                "data": {
                    **ohlcv_data,
                    "timestamp": ohlcv_data["timestamp"].isoformat() if isinstance(ohlcv_data["timestamp"], datetime) else ohlcv_data["timestamp"]
                }
            }
            
            self.kafka_client.send(
                topic=None,
                message=message,
                key=f"{ohlcv_data['instrument_token']}_{ohlcv_data['interval']}"
            )
            
        except Exception as e:
            logger.error(f"Error publishing OHLCV to Kafka: {e}")
    
    def close(self):
        """Cleanup resources"""
        try:
            self.kafka_client.close()
            self.engine.dispose()
            logger.info("OHLCVProcessor closed successfully")
        except Exception as e:
            logger.error(f"Error closing OHLCVProcessor: {e}")
