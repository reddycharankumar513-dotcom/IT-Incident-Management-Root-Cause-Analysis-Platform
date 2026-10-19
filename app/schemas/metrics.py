from datetime import datetime
from typing import List, Dict, Optional
from pydantic import BaseModel
from app.schemas.incident import IncidentResponse

class BreakdownItem(BaseModel):
    name: str
    count: int
    percentage: float

class SlaPerformanceStats(BaseModel):
    total_completed: int
    met_sla_count: int
    missed_sla_count: int
    compliance_rate_pct: float
    active_overdue_count: int
    active_at_risk_count: int

class MetricsSummaryResponse(BaseModel):
    total_incidents: int
    active_incidents: int
    resolved_or_closed: int
    overdue_count: int
    overall_compliance_rate_pct: float
    overall_mttr_hours: float
    overall_mtta_hours: float
    by_severity: List[BreakdownItem]
    by_status: List[BreakdownItem]
    by_priority: List[BreakdownItem]
    by_category: List[BreakdownItem]
    by_assignee: List[BreakdownItem]
    mttr_by_severity: Dict[str, float]

class ExecutiveSummaryReport(BaseModel):
    generated_at: datetime
    operational_health_status: str  # "Healthy", "Warning", "Critical Action Required"
    summary_notes: str
    metrics: MetricsSummaryResponse
    critical_unresolved: List[IncidentResponse]
    overdue_active: List[IncidentResponse]
