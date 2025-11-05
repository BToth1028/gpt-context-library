"""
Timestamp utilities
Enhanced from S03_VECT.py with additional formats
"""

import time
from datetime import datetime, timezone


UTC = timezone.utc


def iso_utc() -> str:
    """
    ISO8601 timestamp with timezone
    SOURCE: S03_VECT.py line 75-76 (_iso_utc)
    Enhanced: Returns ISO8601 with 'Z' suffix
    
    Returns:
        ISO8601 string like "2025-11-05T16:30:00Z"
    """
    return datetime.now(UTC).isoformat().replace('+00:00', 'Z')


def unix_timestamp() -> int:
    """
    Unix epoch timestamp (seconds since 1970-01-01)
    
    Returns:
        Integer timestamp
    """
    return int(time.time())


def date_str() -> str:
    """
    Date string in YYYY-MM-DD format
    SOURCE: S03_VECT.py line 79-80 (_day) - enhanced
    
    Returns:
        Date string like "2025-11-05"
    """
    return datetime.now(UTC).strftime("%Y-%m-%d")


def time_str() -> str:
    """
    Time string in HH:MM:SS format
    
    Returns:
        Time string like "16:30:45"
    """
    return datetime.now(UTC).strftime("%H:%M:%S")


def day_compact() -> str:
    """
    Compact date string for filenames
    SOURCE: S03_VECT.py line 79-80 (_day)
    
    Returns:
        Date string like "20251105"
    """
    return datetime.now().strftime("%Y%m%d")

