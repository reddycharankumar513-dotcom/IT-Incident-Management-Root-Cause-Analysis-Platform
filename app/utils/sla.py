from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple
from app.config import settings
from app.utils.timezone import utc_now

def get_default_sla_targets(severity: str) -> Tuple[float, float]:
    """
    Returns (resolution_sla_hours, response_sla_hours) based on severity.
    """
    resolution_hours = settings.get_resolution_sla_hours(severity)
    response_hours = settings.get_response_sla_hours(severity)
    return resolution_hours, response_hours

def calculate_sla_deadline(created_at: datetime, target_hours: float) -> datetime:
    """Calculates deadline datetime from creation time and target hours."""
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return created_at + timedelta(hours=target_hours)

def calculate_age_hours(created_at: datetime, end_time: Optional[datetime] = None) -> float:
    """Calculates age in hours from created_at until end_time (or utc_now)."""
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    target_end = end_time or utc_now()
    if target_end.tzinfo is None:
        target_end = target_end.replace(tzinfo=timezone.utc)
    diff = (target_end - created_at).total_seconds()
    return max(0.0, round(diff / 3600.0, 2))

def evaluate_sla(
    created_at: datetime,
    resolved_at: Optional[datetime],
    status: str,
    target_hours: float
) -> Tuple[bool, str, float]:
    """
    Evaluates SLA performance for an incident.
    Returns: (is_overdue, sla_status, hours_consumed)
    sla_status options: 'Within SLA', 'At Risk', 'Breached', 'Met SLA', 'Missed SLA'
    """
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    
    if resolved_at is not None and resolved_at.tzinfo is None:
        resolved_at = resolved_at.replace(tzinfo=timezone.utc)

    now = utc_now()
    deadline = calculate_sla_deadline(created_at, target_hours)

    if status in ("Resolved", "Closed"):
        eff_end = resolved_at if resolved_at else now
        consumed = max(0.0, round((eff_end - created_at).total_seconds() / 3600.0, 2))
        if consumed <= target_hours:
            return False, "Met SLA", consumed
        else:
            return True, "Missed SLA", consumed
    else:
        consumed = max(0.0, round((now - created_at).total_seconds() / 3600.0, 2))
        if now > deadline:
            return True, "Breached", consumed
        # If > 75% of time has elapsed, mark as At Risk
        warning_threshold = target_hours * 0.75
        if consumed >= warning_threshold:
            return False, "At Risk", consumed
        return False, "Within SLA", consumed
