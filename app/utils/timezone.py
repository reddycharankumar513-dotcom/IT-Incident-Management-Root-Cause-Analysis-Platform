from datetime import datetime, timezone, timedelta
from typing import Optional

def utc_now() -> datetime:
    """Returns the current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)

def format_iso(dt: Optional[datetime]) -> Optional[str]:
    """Formats datetime as ISO 8601 with Z indicator."""
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def format_duration(seconds: float) -> str:
    """Formats duration in seconds to human-readable string (e.g., '2h 15m' or '3d 4h')."""
    if seconds < 0:
        return "0m"
    total_seconds = int(seconds)
    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600
    minutes = (total_seconds % 3600) // 60
    
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0 or days > 0:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}m")
    
    return " ".join(parts)

def to_user_timezone(dt: Optional[datetime], tz_offset_hours: float = 0.0) -> Optional[str]:
    """Converts UTC datetime to specified user timezone offset for display."""
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    tz = timezone(timedelta(hours=tz_offset_hours))
    converted = dt.astimezone(tz)
    return converted.strftime("%Y-%m-%d %H:%M:%S (UTC%z)")
