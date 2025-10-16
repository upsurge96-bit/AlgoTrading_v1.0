# core/core/models/tick.py
from pydantic import BaseModel, Field, condecimal
from typing import Optional, Dict, Any
from datetime import datetime

class Tick(BaseModel):
    event_id: Optional[str] = Field(None, description="UUID or source unique id")
    symbol: str
    exchange: Optional[str]
    timestamp: datetime  # event time in UTC
    price: Optional[float]
    last_price: Optional[float]
    volume: Optional[float]
    tick_type: Optional[str] = "trade"
    source: Optional[str]
    ingest_ts: Optional[datetime]
    raw: Optional[Dict[str, Any]] = None

    class Config:
        orm_mode = True
        json_encoders = {datetime: lambda v: v.isoformat()}
