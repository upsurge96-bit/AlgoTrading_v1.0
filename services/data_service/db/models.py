"""
Data Service Database Models
SQLAlchemy ORM models for market data storage in TimescaleDB
"""

from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, Float, Boolean, Index, BigInteger, Numeric
from sqlalchemy.dialects.postgresql import JSONB
from core.db.base import Base


class TickData(Base):
    """
    Live tick data from market feed (WebSocket)
    Stores real-time tick data with high frequency
    """
    __tablename__ = "tick_data"
    
    # Primary key - timestamp is the hypertable dimension
    timestamp = Column(DateTime, primary_key=True, nullable=False, index=True)
    instrument_token = Column(BigInteger, primary_key=True, nullable=False, index=True)
    
    # Price data
    last_price = Column(Numeric(precision=12, scale=2), nullable=True)
    last_quantity = Column(Integer, nullable=True)
    average_price = Column(Numeric(precision=12, scale=2), nullable=True)
    volume = Column(BigInteger, nullable=True)
    
    # Buy/Sell data
    buy_quantity = Column(BigInteger, nullable=True)
    sell_quantity = Column(BigInteger, nullable=True)
    
    # OHLC for the day
    open = Column(Numeric(precision=12, scale=2), nullable=True)
    high = Column(Numeric(precision=12, scale=2), nullable=True)
    low = Column(Numeric(precision=12, scale=2), nullable=True)
    close = Column(Numeric(precision=12, scale=2), nullable=True)
    
    # Open Interest (for F&O)
    oi = Column(BigInteger, nullable=True)
    oi_day_high = Column(BigInteger, nullable=True)
    oi_day_low = Column(BigInteger, nullable=True)
    
    # Exchange timestamp
    exchange_timestamp = Column(DateTime, nullable=True)
    
    # Market depth (stored as JSON for flexibility)
    depth = Column(JSONB, nullable=True)
    
    # Metadata
    mode = Column(String(10), nullable=True)  # ltp, quote, full
    tradable = Column(Boolean, default=True)
    
    # Indexes for common queries
    __table_args__ = (
        Index('ix_tick_data_timestamp_token', 'timestamp', 'instrument_token'),
        Index('ix_tick_data_token_timestamp', 'instrument_token', 'timestamp'),
    )
    
    def __repr__(self):
        return f"<TickData(token={self.instrument_token}, time={self.timestamp}, ltp={self.last_price})>"


class OHLCVData(Base):
    """
    OHLCV candle data for different timeframes
    Aggregated data from tick data or historical API
    """
    __tablename__ = "ohlcv_data"
    
    # Primary key - timestamp is the hypertable dimension
    timestamp = Column(DateTime, primary_key=True, nullable=False, index=True)
    instrument_token = Column(BigInteger, primary_key=True, nullable=False, index=True)
    interval = Column(String(20), primary_key=True, nullable=False)  # 1m, 5m, 15m, 1h, 1d
    
    # OHLCV data
    open = Column(Numeric(precision=12, scale=2), nullable=False)
    high = Column(Numeric(precision=12, scale=2), nullable=False)
    low = Column(Numeric(precision=12, scale=2), nullable=False)
    close = Column(Numeric(precision=12, scale=2), nullable=False)
    volume = Column(BigInteger, nullable=False)
    
    # Open Interest (for F&O)
    oi = Column(BigInteger, nullable=True)
    
    # Metadata
    trades = Column(Integer, nullable=True)  # Number of trades in this candle
    
    # Indexes for common queries
    __table_args__ = (
        Index('ix_ohlcv_timestamp_token_interval', 'timestamp', 'instrument_token', 'interval'),
        Index('ix_ohlcv_token_interval_timestamp', 'instrument_token', 'interval', 'timestamp'),
    )
    
    def __repr__(self):
        return f"<OHLCVData(token={self.instrument_token}, interval={self.interval}, time={self.timestamp})>"


class InstrumentMaster(Base):
    """
    Instrument master data
    Stores instrument details from Kite API
    """
    __tablename__ = "instrument_master"
    
    instrument_token = Column(BigInteger, primary_key=True, nullable=False)
    exchange_token = Column(BigInteger, nullable=True)
    
    # Instrument details
    tradingsymbol = Column(String(50), nullable=False, index=True)
    name = Column(String(200), nullable=True)
    exchange = Column(String(10), nullable=False, index=True)
    segment = Column(String(20), nullable=True)
    
    # Instrument type
    instrument_type = Column(String(10), nullable=True)  # EQ, FUT, CE, PE
    
    # Contract details (for F&O)
    expiry = Column(DateTime, nullable=True)
    strike = Column(Numeric(precision=12, scale=2), nullable=True)
    tick_size = Column(Numeric(precision=10, scale=4), nullable=True)
    lot_size = Column(Integer, nullable=True)
    
    # Last update
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Indexes
    __table_args__ = (
        Index('ix_instrument_tradingsymbol', 'tradingsymbol'),
        Index('ix_instrument_exchange', 'exchange'),
        Index('ix_instrument_expiry', 'expiry'),
    )
    
    def __repr__(self):
        return f"<InstrumentMaster(token={self.instrument_token}, symbol={self.tradingsymbol})>"


class DataServiceMetadata(Base):
    """
    Metadata for data service operations
    Tracks data loading status, last sync times, etc.
    """
    __tablename__ = "data_service_metadata"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Metadata key-value
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(String(500), nullable=True)
    
    # Additional data as JSON
    data = Column(JSONB, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<DataServiceMetadata(key={self.key}, value={self.value})>"
