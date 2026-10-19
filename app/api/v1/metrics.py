from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.metrics import (
    MetricsSummaryResponse,
    ExecutiveSummaryReport,
    SlaPerformanceStats,
)
from app.services.metrics_service import MetricsService
from app.security import get_current_user, AuthenticatedUser

router = APIRouter(prefix="/reports", tags=["Reports & Metrics"])

@router.get(
    "/summary",
    response_model=ExecutiveSummaryReport,
    summary="Get executive summary report",
    description="Returns high-level operational health indicators, key metrics, open critical incidents, and active SLA breaches."
)
def get_summary_report(
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
):
    return MetricsService.get_executive_summary_report(db)

@router.get(
    "/metrics",
    response_model=MetricsSummaryResponse,
    summary="Get comprehensive platform metrics",
    description="Aggregates metrics by severity, status, priority, category, assignee, overall MTTR, and MTTR by severity."
)
def get_metrics(
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
):
    return MetricsService.get_metrics_summary(db)

@router.get(
    "/sla-compliance",
    response_model=SlaPerformanceStats,
    summary="Get detailed SLA compliance statistics",
    description="Provides SLA adherence rates for resolved incidents and highlights active at-risk and breached tickets."
)
def get_sla_compliance(
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
):
    return MetricsService.get_sla_stats(db)
