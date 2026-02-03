"""Timezone utilities for AEST handling.

All timestamps in the application use Australian Eastern Standard Time (AEST).
"""
from datetime import datetime
from zoneinfo import ZoneInfo

# AEST timezone (Australia/Brisbane has no daylight saving)
AEST = ZoneInfo("Australia/Brisbane")


def now_aest() -> datetime:
    """Get current datetime in AEST timezone.
    
    Returns:
        Current datetime with AEST timezone info
    """
    return datetime.now(AEST)


def to_aest(dt: datetime) -> datetime:
    """Convert datetime to AEST timezone.
    
    Args:
        dt: Datetime to convert (can be naive or timezone-aware)
        
    Returns:
        Datetime converted to AEST timezone
    """
    if dt.tzinfo is None:
        # Naive datetime, assume it's already in AEST
        return dt.replace(tzinfo=AEST)
    
    # Convert timezone-aware datetime to AEST
    return dt.astimezone(AEST)


def ensure_aest(dt: datetime) -> datetime:
    """Ensure datetime has AEST timezone info.
    
    If datetime is naive, assumes it's in AEST and adds timezone info.
    If datetime is timezone-aware, converts to AEST.
    
    Args:
        dt: Datetime to process
        
    Returns:
        Datetime with AEST timezone info
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=AEST)
    return dt.astimezone(AEST)


def date_to_aest_range(date_str: str) -> tuple[datetime, datetime]:
    """Convert date string to AEST datetime range for that day.
    
    Args:
        date_str: Date string in format YYYY-MM-DD
        
    Returns:
        Tuple of (start_of_day, end_of_day) in AEST timezone
        
    Raises:
        ValueError: If date string format is invalid
    """
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError as e:
        raise ValueError(f"Invalid date format. Expected YYYY-MM-DD, got: {date_str}") from e
    
    # Start of day in AEST (00:00:00)
    start_of_day = datetime.combine(date_obj.date(), datetime.min.time(), tzinfo=AEST)
    
    # End of day in AEST (23:59:59.999999)
    end_of_day = datetime.combine(date_obj.date(), datetime.max.time(), tzinfo=AEST)
    
    return start_of_day, end_of_day