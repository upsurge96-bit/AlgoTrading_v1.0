from datetime import datetime, timezone

def utc_now():
    return datetime.now(timezone.utc)

def timestamp_ms():
    return int(utc_now().timestamp() * 1000)
