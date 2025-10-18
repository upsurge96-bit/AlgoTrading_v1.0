"""
core/db/models.py
-----------------------------------------------------
SQLAlchemy ORM models for database entities.
-----------------------------------------------------
"""

import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Union
from sqlalchemy import Column, String, DateTime, Integer, Float, Boolean, ForeignKey, JSON, Text, LargeBinary
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from core.db.base import Base

class TokenRecord(Base):
    """
    Token record for broker authentication.
    
    Represents an authentication token for a specific broker.
    """
    
    __tablename__ = "token_records"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    broker_id = Column(String, index=True, nullable=False, unique=True)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=True)
    expiry_time = Column(DateTime, nullable=False)
    last_refresh = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Additional metadata for troubleshooting
    refresh_count = Column(Integer, nullable=False, default=0)
    error_count = Column(Integer, nullable=False, default=0)
    last_error = Column(Text, nullable=True)
    token_metadata = Column(JSONB, nullable=True)
    
    def __repr__(self) -> str:
        return f"<TokenRecord(broker_id='{self.broker_id}', expiry='{self.expiry_time}')>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            "id": str(self.id),
            "broker_id": self.broker_id,
            "access_token": self.access_token[:8] + "..." + self.access_token[-8:] if self.access_token else None,
            "refresh_token": self.refresh_token[:4] + "..." + self.refresh_token[-4:] if self.refresh_token else None,
            "expiry_time": self.expiry_time.isoformat() if self.expiry_time else None,
            "last_refresh": self.last_refresh.isoformat() if self.last_refresh else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "refresh_count": self.refresh_count,
            "error_count": self.error_count,
            "is_valid": self.is_valid(),
            "time_to_expiry": self.time_to_expiry().total_seconds() if self.is_valid() else 0
        }
        
    def is_valid(self) -> bool:
        """
        Check if the token is still valid.
        
        Returns:
            True if the token is valid, False otherwise
        """
        from core.utils.time_utils import utc_now
        now = utc_now().replace(tzinfo=None)  # Remove timezone for comparison with naive datetime
        return self.expiry_time > now
    
    def time_to_expiry(self) -> datetime:
        """
        Calculate time to expiry.
        
        Returns:
            Time to expiry or zero timedelta if expired
        """
        from core.utils.time_utils import utc_now
        now = utc_now().replace(tzinfo=None)  # Remove timezone for comparison with naive datetime
        if self.expiry_time > now:
            return self.expiry_time - now
        return timedelta(seconds=0)  # Zero timedelta