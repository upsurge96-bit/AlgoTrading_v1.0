from datetime import datetime, timezone, timedelta
from typing import Union, Optional

def utc_now():
    """Return current UTC datetime with timezone information."""
    return datetime.now(timezone.utc)

def timestamp_ms():
    """Return current UTC timestamp in milliseconds."""
    return int(utc_now().timestamp() * 1000)

def timestamp_s():
    """Return current UTC timestamp in seconds."""
    return int(utc_now().timestamp())

def format_iso(dt: Optional[datetime] = None) -> str:
    """Convert datetime to ISO 8601 format with timezone."""
    if dt is None:
        dt = utc_now()
    # Ensure datetime has timezone
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()

def parse_datetime(dt_str: str) -> datetime:
    """Parse datetime string in various formats to datetime object."""
    formats = [
        "%Y-%m-%dT%H:%M:%S.%f%z",  # ISO format with microseconds and timezone
        "%Y-%m-%dT%H:%M:%S%z",      # ISO format without microseconds but with timezone
        "%Y-%m-%dT%H:%M:%S.%f",     # ISO format with microseconds no timezone
        "%Y-%m-%dT%H:%M:%S",        # ISO format without microseconds or timezone
        "%Y-%m-%d %H:%M:%S.%f",     # Format often used in databases
        "%Y-%m-%d %H:%M:%S",        # Simple datetime format
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(dt_str, fmt)
            # Add timezone if missing
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
            
    # If all formats fail, try fromisoformat
    try:
        dt = datetime.fromisoformat(dt_str)
        # Add timezone if missing
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        pass
    
    raise ValueError(f"Cannot parse datetime string: {dt_str}")

def datetime_to_timestamp(dt: Optional[datetime] = None) -> float:
    """Convert datetime to UNIX timestamp in seconds."""
    if dt is None:
        dt = utc_now()
    # Ensure datetime has timezone
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()

def timestamp_to_datetime(timestamp: Union[int, float]) -> datetime:
    """Convert UNIX timestamp to datetime with UTC timezone."""
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)
