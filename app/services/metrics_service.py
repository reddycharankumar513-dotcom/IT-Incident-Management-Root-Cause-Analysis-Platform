from datetime import datetime
from collections import defaultdict
from typing import List, Dict
from sqlalchemy.orm import Session

from app.models.incident import Incident
from app.schemas.metrics import (
    BreakdownItem,
    MetricsSummaryResponse,
    ExecutiveSummaryReport,
    SlaPerformanceStats,
)
from app.schemas.incident import IncidentResponse
from app.schemas.common import IncidentStatusEnum, SeverityEnum
from app.services.incident_service import IncidentService
from app.utils.timezone import utc_now

class MetricsService:
    @classmethod
    def get_metrics_summary(cls, db: Session) -> MetricsSummaryResponse:
        all_incidents = db.query(Incident).all()
        total = len(all_incidents)

        if total == 0:
            return MetricsSummaryResponse(
                total_incidents=0,
                active_incidents=0,
                resolved_or_closed=0,
                overdue_count=0,
                overall_compliance_rate_pct=100.0,
                overall_mttr_hours=0.0,
                overall_mtta_hours=0.0,
                by_severity=[],
                by_status=[],
                by_priority=[],
                by_category=[],
                by_assignee=[],
                mttr_by_severity={},
            )

        active_statuses = {
            IncidentStatusEnum.OPEN.value,
            IncidentStatusEnum.IN_PROGRESS.value,
            IncidentStatusEnum.PENDING.value,
        }
        completed_statuses = {
            IncidentStatusEnum.RESOLVED.value,
            IncidentStatusEnum.CLOSED.value,
        }

        active_count = 0
        completed_count = 0
        overdue_count = 0
        met_sla_count = 0

        severity_counts = defaultdict(int)
        status_counts = defaultdict(int)
        priority_counts = defaultdict(int)
        category_counts = defaultdict(int)
        assignee_counts = defaultdict(int)

        ttr_values = []
        tta_values = []
        ttr_by_sev = defaultdict(list)

        enriched_records = [IncidentService.enrich_incident_response(inc) for inc in all_incidents]

        for item in enriched_records:
            st = item["status"]
            sev = item["severity"]
            pri = item["priority"]
            cat = item["category"]
            asn = item["assignee"] or "Unassigned"

            severity_counts[sev] += 1
            status_counts[st] += 1
            priority_counts[pri] += 1
            category_counts[cat] += 1
            assignee_counts[asn] += 1

            if st in active_statuses:
                active_count += 1
            elif st in completed_statuses:
                completed_count += 1

            if item["is_overdue"]:
                overdue_count += 1

            if item["sla_status"] == "Met SLA":
                met_sla_count += 1

            if item["time_to_resolve_hours"] is not None:
                ttr_values.append(item["time_to_resolve_hours"])
                ttr_by_sev[sev].append(item["time_to_resolve_hours"])

            if item["time_to_acknowledge_hours"] is not None:
                tta_values.append(item["time_to_acknowledge_hours"])

        # Compliance rate on completed incidents
        if completed_count > 0:
            compliance_rate = round((met_sla_count / completed_count) * 100.0, 1)
        else:
            compliance_rate = 100.0 if overdue_count == 0 else 0.0

        overall_mttr = round(sum(ttr_values) / len(ttr_values), 2) if ttr_values else 0.0
        overall_mtta = round(sum(tta_values) / len(tta_values), 2) if tta_values else 0.0

        mttr_by_severity_dict = {
            sev: round(sum(vals) / len(vals), 2)
            for sev, vals in ttr_by_sev.items()
            if vals
        }

        def build_breakdown(counts: Dict[str, int]) -> List[BreakdownItem]:
            items = []
            for name, cnt in sorted(counts.items(), key=lambda x: x[1], reverse=True):
                pct = round((cnt / total) * 100.0, 1)
                items.append(BreakdownItem(name=name, count=cnt, percentage=pct))
            return items

        return MetricsSummaryResponse(
            total_incidents=total,
            active_incidents=active_count,
            resolved_or_closed=completed_count,
            overdue_count=overdue_count,
            overall_compliance_rate_pct=compliance_rate,
            overall_mttr_hours=overall_mttr,
            overall_mtta_hours=overall_mtta,
            by_severity=build_breakdown(severity_counts),
            by_status=build_breakdown(status_counts),
            by_priority=build_breakdown(priority_counts),
            by_category=build_breakdown(category_counts),
            by_assignee=build_breakdown(assignee_counts),
            mttr_by_severity=mttr_by_severity_dict,
        )

    @classmethod
    def get_sla_stats(cls, db: Session) -> SlaPerformanceStats:
        all_incidents = db.query(Incident).all()
        enriched = [IncidentService.enrich_incident_response(inc) for inc in all_incidents]

        completed_count = 0
        met_count = 0
        missed_count = 0
        active_overdue = 0
        active_at_risk = 0

        for item in enriched:
            st = item["status"]
            sla_st = item["sla_status"]
            if st in (IncidentStatusEnum.RESOLVED.value, IncidentStatusEnum.CLOSED.value):
                completed_count += 1
                if sla_st == "Met SLA":
                    met_count += 1
                else:
                    missed_count += 1
            else:
                if sla_st == "Breached":
                    active_overdue += 1
                elif sla_st == "At Risk":
                    active_at_risk += 1

        compliance = round((met_count / completed_count * 100.0), 1) if completed_count > 0 else 100.0

        return SlaPerformanceStats(
            total_completed=completed_count,
            met_sla_count=met_count,
            missed_sla_count=missed_count,
            compliance_rate_pct=compliance,
            active_overdue_count=active_overdue,
            active_at_risk_count=active_at_risk,
        )

    @classmethod
    def get_executive_summary_report(cls, db: Session) -> ExecutiveSummaryReport:
        now = utc_now()
        metrics = cls.get_metrics_summary(db)
        all_incidents = db.query(Incident).all()
        enriched = [IncidentService.enrich_incident_response(inc) for inc in all_incidents]

        active_statuses = {
            IncidentStatusEnum.OPEN.value,
            IncidentStatusEnum.IN_PROGRESS.value,
            IncidentStatusEnum.PENDING.value,
        }

        critical_unresolved = [
            IncidentResponse(**item)
            for item in enriched
            if item["status"] in active_statuses and item["severity"] == SeverityEnum.CRITICAL.value
        ]

        overdue_active = [
            IncidentResponse(**item)
            for item in enriched
            if item["status"] in active_statuses and item["is_overdue"]
        ]

        if len(critical_unresolved) > 0 or len(overdue_active) > 2:
            status_label = "Critical Action Required"
            notes = (
                f"Attention needed: {len(critical_unresolved)} critical incident(s) currently open "
                f"and {len(overdue_active)} active incident(s) currently breaching SLA resolution targets."
            )
        elif len(overdue_active) > 0 or metrics.overall_compliance_rate_pct < 85.0:
            status_label = "Warning"
            notes = (
                f"Elevated risk: {len(overdue_active)} incident(s) overdue. "
                f"SLA compliance rate is currently at {metrics.overall_compliance_rate_pct}%."
            )
        else:
            status_label = "Healthy"
            notes = (
                f"Operations nominal. SLA compliance rate is at {metrics.overall_compliance_rate_pct}%. "
                f"Mean Time To Resolve (MTTR) is {metrics.overall_mttr_hours} hours."
            )

        return ExecutiveSummaryReport(
            generated_at=now,
            operational_health_status=status_label,
            summary_notes=notes,
            metrics=metrics,
            critical_unresolved=critical_unresolved,
            overdue_active=overdue_active,
        )
