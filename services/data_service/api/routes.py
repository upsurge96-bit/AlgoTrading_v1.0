"""
Data Service API Routes
FastAPI endpoints for data queries, WebSocket control, and service monitoring
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker
import os

from core.utils.logger import get_logger
from services.data_service.db.models import TickData, OHLCVData, InstrumentMaster, DataServiceMetadata
from services.data_service.api.schemas import TickResponse, OHLCVResponse, InstrumentResponse, StatsResponse

logger = get_logger("data_service.api")

router = APIRouter()

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://trader:traderpass@timescaledb:5432/trading")
engine = create_engine(DATABASE_URL, pool_size=10, max_overflow=20)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Dependency to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    logger.debug("💓 Health check endpoint called")
    return {"status": "ok", "service": "data-service", "timestamp": datetime.utcnow().isoformat()}


@router.get("/ticks/latest", response_model=List[TickResponse])
async def get_latest_ticks(
    instrument_tokens: str = Query(..., description="Comma-separated instrument tokens"),
    db: Session = Depends(get_db)
):
    """
    Get latest tick for given instruments
    
    Args:
        instrument_tokens: Comma-separated list of instrument tokens
    """
    try:
        tokens = [int(t.strip()) for t in instrument_tokens.split(",")]
        
        results = []
        for token in tokens:
            tick = db.query(TickData).filter(
                TickData.instrument_token == token
            ).order_by(desc(TickData.timestamp)).first()
            
            if tick:
                results.append(tick)
        
        return results
        
    except Exception as e:
        logger.error(f"Error fetching latest ticks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ticks/history", response_model=List[TickResponse])
async def get_tick_history(
    instrument_token: int = Query(..., description="Instrument token"),
    from_time: Optional[datetime] = Query(None, description="Start time"),
    to_time: Optional[datetime] = Query(None, description="End time"),
    limit: int = Query(1000, description="Maximum number of records"),
    db: Session = Depends(get_db)
):
    """
    Get historical tick data for an instrument
    
    Args:
        instrument_token: Instrument token
        from_time: Start timestamp (defaults to 1 hour ago)
        to_time: End timestamp (defaults to now)
        limit: Maximum number of records
    """
    try:
        # Default time range
        if not to_time:
            to_time = datetime.utcnow()
        if not from_time:
            from_time = to_time - timedelta(hours=1)
        
        query = db.query(TickData).filter(
            TickData.instrument_token == instrument_token,
            TickData.timestamp >= from_time,
            TickData.timestamp <= to_time
        ).order_by(desc(TickData.timestamp)).limit(limit)
        
        results = query.all()
        
        return results
        
    except Exception as e:
        logger.error(f"Error fetching tick history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ohlcv", response_model=List[OHLCVResponse])
async def get_ohlcv(
    instrument_token: int = Query(..., description="Instrument token"),
    interval: str = Query(..., description="Interval (1m, 5m, 15m, 1h, 1d)"),
    from_time: Optional[datetime] = Query(None, description="Start time"),
    to_time: Optional[datetime] = Query(None, description="End time"),
    limit: int = Query(500, description="Maximum number of records"),
    db: Session = Depends(get_db)
):
    """
    Get OHLCV candle data for an instrument
    
    Args:
        instrument_token: Instrument token
        interval: Interval (1m, 5m, 15m, 1h, 1d)
        from_time: Start timestamp
        to_time: End timestamp
        limit: Maximum number of records
    """
    try:
        # Default time range based on interval
        if not to_time:
            to_time = datetime.utcnow()
        if not from_time:
            if interval == "1d":
                from_time = to_time - timedelta(days=365)
            elif interval == "1h":
                from_time = to_time - timedelta(days=30)
            else:
                from_time = to_time - timedelta(days=7)
        
        query = db.query(OHLCVData).filter(
            OHLCVData.instrument_token == instrument_token,
            OHLCVData.interval == interval,
            OHLCVData.timestamp >= from_time,
            OHLCVData.timestamp <= to_time
        ).order_by(desc(OHLCVData.timestamp)).limit(limit)
        
        results = query.all()
        
        # Reverse to get chronological order
        results.reverse()
        
        return results
        
    except Exception as e:
        logger.error(f"Error fetching OHLCV data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/instruments", response_model=List[InstrumentResponse])
async def get_instruments(
    exchange: Optional[str] = Query(None, description="Exchange (NSE, BSE, NFO, etc.)"),
    search: Optional[str] = Query(None, description="Search by trading symbol"),
    limit: int = Query(100, description="Maximum number of records"),
    db: Session = Depends(get_db)
):
    """
    Get instrument master data
    
    Args:
        exchange: Filter by exchange
        search: Search by trading symbol
        limit: Maximum number of records
    """
    try:
        query = db.query(InstrumentMaster)
        
        if exchange:
            query = query.filter(InstrumentMaster.exchange == exchange.upper())
        
        if search:
            query = query.filter(InstrumentMaster.tradingsymbol.ilike(f"%{search}%"))
        
        results = query.limit(limit).all()
        
        return results
        
    except Exception as e:
        logger.error(f"Error fetching instruments: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/instruments/{instrument_token}", response_model=InstrumentResponse)
async def get_instrument(
    instrument_token: int,
    db: Session = Depends(get_db)
):
    """
    Get instrument details by token
    
    Args:
        instrument_token: Instrument token
    """
    try:
        instrument = db.query(InstrumentMaster).filter(
            InstrumentMaster.instrument_token == instrument_token
        ).first()
        
        if not instrument:
            raise HTTPException(status_code=404, detail="Instrument not found")
        
        return instrument
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching instrument: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=StatsResponse)
async def get_stats(db: Session = Depends(get_db)):
    """
    Get data service statistics
    """
    try:
        # Count total ticks
        tick_count = db.query(TickData).count()
        
        # Count total OHLCV records
        ohlcv_count = db.query(OHLCVData).count()
        
        # Count instruments
        instrument_count = db.query(InstrumentMaster).count()
        
        # Get latest tick timestamp
        latest_tick = db.query(TickData).order_by(desc(TickData.timestamp)).first()
        latest_tick_time = latest_tick.timestamp if latest_tick else None
        
        # Get metadata
        metadata = db.query(DataServiceMetadata).all()
        metadata_dict = {m.key: m.value for m in metadata}
        
        return {
            "tick_count": tick_count,
            "ohlcv_count": ohlcv_count,
            "instrument_count": instrument_count,
            "latest_tick_time": latest_tick_time,
            "metadata": metadata_dict,
            "timestamp": datetime.utcnow()
        }
        
    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# WebSocket control endpoints
class SubscribeRequest(BaseModel):
    instrument_tokens: List[int]
    mode: str = "full"


class UnsubscribeRequest(BaseModel):
    instrument_tokens: List[int]


@router.post("/websocket/subscribe")
async def subscribe_instruments(request: SubscribeRequest):
    """
    Subscribe to instruments on WebSocket
    
    Note: This requires the worker to be running
    """
    try:
        # This would interact with the running worker
        # For now, return success
        logger.info(f"Subscribe request: {request.instrument_tokens}, mode: {request.mode}")
        
        return {
            "status": "success",
            "message": f"Subscribed to {len(request.instrument_tokens)} instruments",
            "instrument_tokens": request.instrument_tokens,
            "mode": request.mode
        }
        
    except Exception as e:
        logger.error(f"Error subscribing: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/websocket/unsubscribe")
async def unsubscribe_instruments(request: UnsubscribeRequest):
    """
    Unsubscribe from instruments on WebSocket
    
    Note: This requires the worker to be running
    """
    try:
        # This would interact with the running worker
        # For now, return success
        logger.info(f"Unsubscribe request: {request.instrument_tokens}")
        
        return {
            "status": "success",
            "message": f"Unsubscribed from {len(request.instrument_tokens)} instruments",
            "instrument_tokens": request.instrument_tokens
        }
        
    except Exception as e:
        logger.error(f"Error unsubscribing: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Historical data fetch endpoints
class HistoricalFetchRequest(BaseModel):
    instrument_tokens: List[int]
    years: int = 5


@router.post("/historical/fetch")
async def trigger_historical_fetch(request: HistoricalFetchRequest):
    """
    Trigger historical data fetch
    
    Note: This is an async operation
    """
    try:
        logger.info(f"Historical fetch request: {len(request.instrument_tokens)} instruments, {request.years} years")
        
        # This would trigger the historical worker
        # For now, return success
        
        return {
            "status": "success",
            "message": f"Triggered historical fetch for {len(request.instrument_tokens)} instruments",
            "instrument_tokens": request.instrument_tokens,
            "years": request.years
        }
        
    except Exception as e:
        logger.error(f"Error triggering historical fetch: {e}")
        raise HTTPException(status_code=500, detail=str(e))


