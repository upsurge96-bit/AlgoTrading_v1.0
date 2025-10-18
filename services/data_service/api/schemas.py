"""
Data Service API Schemas
Pydantic models for API request/response validation
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime


class TickResponse(BaseModel):
    """Response model for tick data"""
    timestamp: datetime
    instrument_token: int
    last_price: Optional[float] = None
    last_quantity: Optional[int] = None
    average_price: Optional[float] = None
    volume: Optional[int] = None
    buy_quantity: Optional[int] = None
    sell_quantity: Optional[int] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    oi: Optional[int] = None
    oi_day_high: Optional[int] = None
    oi_day_low: Optional[int] = None
    exchange_timestamp: Optional[datetime] = None
    mode: Optional[str] = None
    
    class Config:
        orm_mode = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class OHLCVResponse(BaseModel):
    """Response model for OHLCV data"""
    timestamp: datetime
    instrument_token: int
    interval: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    oi: Optional[int] = None
    trades: Optional[int] = None
    
    class Config:
        orm_mode = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class InstrumentResponse(BaseModel):
    """Response model for instrument master data"""
    instrument_token: int
    exchange_token: Optional[int] = None
    tradingsymbol: str
    name: Optional[str] = None
    exchange: str
    segment: Optional[str] = None
    instrument_type: Optional[str] = None
    expiry: Optional[datetime] = None
    strike: Optional[float] = None
    tick_size: Optional[float] = None
    lot_size: Optional[int] = None
    last_updated: Optional[datetime] = None
    
    class Config:
        orm_mode = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class StatsResponse(BaseModel):
    """Response model for service statistics"""
    tick_count: int
    ohlcv_count: int
    instrument_count: int
    latest_tick_time: Optional[datetime] = None
    metadata: Dict[str, Any] = {}
    timestamp: datetime
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class HealthResponse(BaseModel):
    """Response model for health check"""
    status: str
    service: str
    timestamp: str


class SubscriptionRequest(BaseModel):
    """Request model for WebSocket subscription"""
    instrument_tokens: list[int] = Field(..., description="List of instrument tokens to subscribe")
    mode: str = Field(default="full", description="Subscription mode: ltp, quote, or full")


class HistoricalFetchRequest(BaseModel):
    """Request model for historical data fetch"""
    instrument_tokens: list[int] = Field(..., description="List of instrument tokens")
    years: int = Field(default=5, description="Number of years to fetch", ge=1, le=10)
    intervals: list[str] = Field(default=["day", "60minute", "15minute"], description="Intervals to fetch")
