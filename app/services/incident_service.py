from datetime import datetime, timezone
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc, func
from fastapi import HTTPException, status

from app.models.incident import Incident
from app.models.activity import IncidentActivity
from app.schemas.incident import (
    IncidentCreate,
    IncidentUpdate,
    StatusTransitionRequest,
    IncidentResponse,
    IncidentDetailResponse,
)
from app.schemas.common import SeverityEnum, PriorityEnum, IncidentStatusEnum, UserRole
from app.schemas.activity import IncidentActivityResponse
from app.schemas.note import InvestigationNoteResponse
from app.utils.sla import get_default_sla_targets, calculate_sla_deadline, calculate_age_hours, evaluate_sla
from app.utils.timezone import utc_now, format_duration
from app.logging_config import logger

ALLOWED_TRANSITIONS = {
    IncidentStatusEnum.OPEN.value: [IncidentStatusEnum.IN_PROGRESS.value, IncidentStatusEnum.PENDING.value],
    IncidentStatusEnum.IN_PROGRESS.value: [IncidentStatusEnum.PENDING.value, IncidentStatusEnum.RESOLVED.value],
    IncidentStatusEnum.PENDING.value: [IncidentStatusEnum.IN_PROGRESS.value, IncidentStatusEnum.RESOLVED.value],
    IncidentStatusEnum.RESOLVED.value: [IncidentStatusEnum.CLOSED.value, IncidentStatusEnum.IN_PROGRESS.value],
    IncidentStatusEnum.CLOSED.value: [IncidentStatusEnum.IN_PROGRESS.value],
}

DEFAULT_PRIORITY_MAP = {
    SeverityEnum.CRITICAL.value: PriorityEnum.P1.value,
    SeverityEnum.HIGH.value: PriorityEnum.P2.value,
    SeverityEnum.MEDIUM.value: PriorityEnum.P3.value,
    SeverityEnum.LOW.value: PriorityEnum.P4.value,
}

class IncidentService:
    @staticmethod
    def generate_incident_number(db: Session) -> str:
        """Generates sequential incident number e.g. INC-2026-0001."""
        current_year = utc_now().year
        count = db.query(func.count(Incident.id)).scalar() or 0
        return f"INC-{current_year}-{(count + 1):04d}"

    @classmethod
    def enrich_incident_response(cls, inc: Incident) -> dict:
        """Calculates dynamic SLA and age fields for IncidentResponse."""
        target_resolution_hours = inc.sla_resolution_target_hours
        created_at = inc.created_at
        resolved_at = inc.resolved_at
        closed_at = inc.closed_at
        acknowledged_at = inc.acknowledged_at

        # Calculate SLA performance
        is_overdue, sla_status_val, _ = evaluate_sla(
            created_at=created_at,
            resolved_at=resolved_at,
            status=inc.status,
            target_hours=target_resolution_hours
        )

        deadline = calculate_sla_deadline(created_at, target_resolution_hours)
        age_hrs = calculate_age_hours(created_at, closed_at if inc.status == IncidentStatusEnum.CLOSED.value else None)
        age_str = format_duration(age_hrs * 3600)

        # Time to resolve in hours
        ttr_hours = None
        if resolved_at:
            ttr_hours = max(0.0, round((resolved_at - created_at).total_seconds() / 3600.0, 2))

        # Time to acknowledge in hours
        tta_hours = None
        if acknowledged_at:
            tta_hours = max(0.0, round((acknowledged_at - created_at).total_seconds() / 3600.0, 2))

        return {
            "id": inc.id,
            "incident_number": inc.incident_number,
            "title": inc.title,
            "description": inc.description,
            "category": inc.category,
            "subcategory": inc.subcategory,
            "severity": inc.severity,
            "priority": inc.priority,
            "impact": inc.impact,
            "urgency": inc.urgency,
            "status": inc.status,
            "pending_reason": inc.pending_reason,
            "service": inc.service,
            "reporter": inc.reporter,
            "assignee": inc.assignee,
            "assignment_group": inc.assignment_group,
            "root_cause": inc.root_cause,
            "corrective_action": inc.corrective_action,
            "preventive_action": inc.preventive_action,
            "resolution_summary": inc.resolution_summary,
            "sla_resolution_target_hours": inc.sla_resolution_target_hours,
            "sla_response_target_hours": inc.sla_response_target_hours,
            "created_at": inc.created_at,
            "updated_at": inc.updated_at,
            "acknowledged_at": inc.acknowledged_at,
            "resolved_at": inc.resolved_at,
            "closed_at": inc.closed_at,
            "age_hours": age_hrs,
            "age_human_readable": age_str,
            "time_to_resolve_hours": ttr_hours,
            "time_to_acknowledge_hours": tta_hours,
            "sla_deadline": deadline,
            "is_overdue": is_overdue,
            "sla_status": sla_status_val,
        }

    @classmethod
    def create_incident(cls, db: Session, payload: IncidentCreate, performed_by: str) -> IncidentResponse:
        now = utc_now()
        inc_number = cls.generate_incident_number(db)
        
        # Determine priority if not specified
        priority = payload.priority.value if payload.priority else DEFAULT_PRIORITY_MAP.get(payload.severity.value, "P3")
        
        # Calculate default SLAs if not specified
        default_res, default_resp = get_default_sla_targets(payload.severity.value)
        sla_res = payload.sla_resolution_target_hours if payload.sla_resolution_target_hours is not None else default_res
        sla_resp = payload.sla_response_target_hours if payload.sla_response_target_hours is not None else default_resp

        # Create record
        incident = Incident(
            incident_number=inc_number,
            title=payload.title,
            description=payload.description,
            category=payload.category,
            subcategory=payload.subcategory,
            severity=payload.severity.value,
            priority=priority,
            impact=payload.impact.value,
            urgency=payload.urgency.value,
            status=IncidentStatusEnum.OPEN.value,
            service=payload.service,
            reporter=payload.reporter,
            assignee=payload.assignee,
            assignment_group=payload.assignment_group,
            sla_resolution_target_hours=sla_res,
            sla_response_target_hours=sla_resp,
            created_at=now,
            updated_at=now,
        )

        db.add(incident)
        db.flush()

        # Record activity
        activity = IncidentActivity(
            incident_id=incident.id,
            action="CREATED",
            field_name="status",
            old_value=None,
            new_value=IncidentStatusEnum.OPEN.value,
            performed_by=performed_by,
            notes=f"Incident {inc_number} reported by {payload.reporter} with severity {payload.severity.value}",
            timestamp=now
        )
        db.add(activity)

        if payload.assignee:
            assign_act = IncidentActivity(
                incident_id=incident.id,
                action="ASSIGNED",
                field_name="assignee",
                old_value=None,
                new_value=payload.assignee,
                performed_by=performed_by,
                notes=f"Initial assignment to {payload.assignee}",
                timestamp=now
            )
            db.add(assign_act)

        db.commit()
        db.refresh(incident)
        logger.info(f"Created incident {incident.incident_number} - {incident.title}")
        return IncidentResponse(**cls.enrich_incident_response(incident))

    @classmethod
    def get_incident_by_identifier(cls, db: Session, identifier: str) -> Incident:
        """Retrieves incident by internal ID or incident_number."""
        if identifier.isdigit():
            incident = db.query(Incident).filter(Incident.id == int(identifier)).first()
        else:
            incident = db.query(Incident).filter(Incident.incident_number == identifier).first()

        if not incident:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Incident '{identifier}' not found"
            )
        return incident

    @classmethod
    def get_incident_detail(cls, db: Session, identifier: str) -> IncidentDetailResponse:
        incident = cls.get_incident_by_identifier(db, identifier)
        enriched = cls.enrich_incident_response(incident)
        
        enriched["notes"] = [
            InvestigationNoteResponse.model_validate(n) for n in incident.notes
        ]
        enriched["activities"] = [
            IncidentActivityResponse.model_validate(a) for a in incident.activities
        ]
        return IncidentDetailResponse(**enriched)

    @classmethod
    def list_incidents(
        cls,
        db: Session,
        search: Optional[str] = None,
        status_filter: Optional[str] = None,
        severity_filter: Optional[str] = None,
        priority_filter: Optional[str] = None,
        category_filter: Optional[str] = None,
        assignee_filter: Optional[str] = None,
        reporter_filter: Optional[str] = None,
        service_filter: Optional[str] = None,
        is_overdue_filter: Optional[bool] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[IncidentResponse], int]:
        query = db.query(Incident)

        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    Incident.title.ilike(search_term),
                    Incident.description.ilike(search_term),
                    Incident.incident_number.ilike(search_term),
                    Incident.service.ilike(search_term),
                    Incident.root_cause.ilike(search_term),
                )
            )

        if status_filter:
            query = query.filter(Incident.status == status_filter)
        if severity_filter:
            query = query.filter(Incident.severity == severity_filter)
        if priority_filter:
            query = query.filter(Incident.priority == priority_filter)
        if category_filter:
            query = query.filter(Incident.category.ilike(f"%{category_filter}%"))
        if assignee_filter:
            query = query.filter(Incident.assignee.ilike(f"%{assignee_filter}%"))
        if reporter_filter:
            query = query.filter(Incident.reporter.ilike(f"%{reporter_filter}%"))
        if service_filter:
            query = query.filter(Incident.service.ilike(f"%{service_filter}%"))

        query = query.order_by(desc(Incident.created_at))

        all_records = query.all()

        # Process SLA & overdue metrics
        enriched_list = [cls.enrich_incident_response(inc) for inc in all_records]

        # In-memory filter for computed is_overdue if requested
        if is_overdue_filter is not None:
            enriched_list = [e for e in enriched_list if e["is_overdue"] == is_overdue_filter]

        total = len(enriched_list)
        start = (page - 1) * page_size
        end = start + page_size
        paginated_items = enriched_list[start:end]

        return [IncidentResponse(**item) for item in paginated_items], total

    @classmethod
    def update_incident(
        cls,
        db: Session,
        identifier: str,
        payload: IncidentUpdate,
        performed_by: str,
    ) -> IncidentResponse:
        incident = cls.get_incident_by_identifier(db, identifier)
        now = utc_now()
        changes = payload.model_dump(exclude_unset=True)

        if not changes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one field must be provided for update"
            )

        # Disallow direct modification if closed
        if incident.status == IncidentStatusEnum.CLOSED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Closed incidents cannot be modified. Reopen the incident first."
            )

        for field, new_val in changes.items():
            old_val = getattr(incident, field)
            # Handle enums
            if hasattr(new_val, "value"):
                new_val = new_val.value

            if old_val != new_val:
                setattr(incident, field, new_val)
                # Log activity
                activity = IncidentActivity(
                    incident_id=incident.id,
                    action="UPDATED",
                    field_name=field,
                    old_value=str(old_val) if old_val is not None else None,
                    new_value=str(new_val) if new_val is not None else None,
                    performed_by=performed_by,
                    notes=f"Updated {field} to '{new_val}'",
                    timestamp=now
                )
                db.add(activity)

        incident.updated_at = now
        db.commit()
        db.refresh(incident)
        logger.info(f"Updated incident {incident.incident_number} by {performed_by}")
        return IncidentResponse(**cls.enrich_incident_response(incident))

    @classmethod
    def transition_status(
        cls,
        db: Session,
        identifier: str,
        payload: StatusTransitionRequest,
        performed_by: str,
        user_role: UserRole,
    ) -> IncidentResponse:
        incident = cls.get_incident_by_identifier(db, identifier)
        now = utc_now()
        current_status = incident.status
        target_status = payload.status.value

        if current_status == target_status:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Incident is already in status '{target_status}'"
            )

        # Validate transition matrix
        allowed_next = ALLOWED_TRANSITIONS.get(current_status, [])
        if target_status not in allowed_next:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status transition from '{current_status}' to '{target_status}'. Allowed: {allowed_next}"
            )

        # Reopening a closed incident requires Admin role
        if current_status == IncidentStatusEnum.CLOSED.value and target_status == IncidentStatusEnum.IN_PROGRESS.value:
            if user_role != UserRole.ADMIN:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only Administrators can reopen Closed incidents."
                )

        # Apply specific status transition behaviors
        if target_status == IncidentStatusEnum.IN_PROGRESS.value:
            if incident.acknowledged_at is None:
                incident.acknowledged_at = now
            if current_status in (IncidentStatusEnum.RESOLVED.value, IncidentStatusEnum.CLOSED.value):
                # Reopening
                incident.resolved_at = None
                incident.closed_at = None
                action_name = "REOPENED"
            else:
                action_name = "STATUS_CHANGED"
        elif target_status == IncidentStatusEnum.PENDING.value:
            incident.pending_reason = payload.pending_reason
            action_name = "STATUS_CHANGED"
        elif target_status == IncidentStatusEnum.RESOLVED.value:
            incident.resolved_at = now
            incident.resolution_summary = payload.resolution_summary
            if payload.root_cause:
                incident.root_cause = payload.root_cause
            if payload.corrective_action:
                incident.corrective_action = payload.corrective_action
            if payload.preventive_action:
                incident.preventive_action = payload.preventive_action
            incident.pending_reason = None
            action_name = "RESOLVED"
        elif target_status == IncidentStatusEnum.CLOSED.value:
            incident.closed_at = now
            action_name = "CLOSED"
        else:
            action_name = "STATUS_CHANGED"

        incident.status = target_status
        incident.updated_at = now

        # Add activity record
        activity = IncidentActivity(
            incident_id=incident.id,
            action=action_name,
            field_name="status",
            old_value=current_status,
            new_value=target_status,
            performed_by=performed_by,
            notes=payload.reason or f"Transitioned status to {target_status}",
            timestamp=now
        )
        db.add(activity)

        db.commit()
        db.refresh(incident)
        logger.info(f"Transitioned incident {incident.incident_number} from {current_status} to {target_status}")
        return IncidentResponse(**cls.enrich_incident_response(incident))
