from typing import Optional, List
from fastapi import APIRouter, Depends, Query, Path, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.incident import (
    IncidentCreate,
    IncidentUpdate,
    StatusTransitionRequest,
    IncidentResponse,
    IncidentDetailResponse,
)
from app.schemas.common import PaginatedResponse, UserRole
from app.services.incident_service import IncidentService
from app.security import get_current_user, require_role, AuthenticatedUser

router = APIRouter(prefix="/incidents", tags=["Incidents"])

@router.post(
    "",
    response_model=IncidentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new IT incident",
    description="Registers a new incident with automatic ID assignment (e.g. INC-2026-0001), priority calculation, and SLA targets."
)
def create_incident(
    payload: IncidentCreate,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_role([UserRole.ADMIN, UserRole.ENGINEER])),
):
    return IncidentService.create_incident(db, payload, performed_by=user.username)

@router.get(
    "",
    response_model=PaginatedResponse[IncidentResponse],
    summary="List, search, and filter incidents",
    description="List incidents with filtering by status, severity, priority, category, assignee, overdue status, and full-text keyword search."
)
def list_incidents(
    search: Optional[str] = Query(None, description="Search keyword across title, description, incident ID, service, or root cause"),
    status: Optional[str] = Query(None, description="Filter by status: Open, In Progress, Pending, Resolved, Closed"),
    severity: Optional[str] = Query(None, description="Filter by severity: Critical, High, Medium, Low"),
    priority: Optional[str] = Query(None, description="Filter by priority: P1, P2, P3, P4"),
    category: Optional[str] = Query(None, description="Filter by category (e.g., Software, Hardware, Network)"),
    assignee: Optional[str] = Query(None, description="Filter by assigned engineer"),
    reporter: Optional[str] = Query(None, description="Filter by reporting person/system"),
    service: Optional[str] = Query(None, description="Filter by affected service"),
    is_overdue: Optional[bool] = Query(None, description="Filter by SLA overdue status (true/false)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Page size"),
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
):
    items, total = IncidentService.list_incidents(
        db=db,
        search=search,
        status_filter=status,
        severity_filter=severity,
        priority_filter=priority,
        category_filter=category,
        assignee_filter=assignee,
        reporter_filter=reporter,
        service_filter=service,
        is_overdue_filter=is_overdue,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse[IncidentResponse](
        total=total,
        page=page,
        page_size=page_size,
        items=items,
    )

@router.get(
    "/overdue",
    response_model=List[IncidentResponse],
    summary="Get all overdue active incidents",
    description="Retrieves all currently active incidents (Open, In Progress, Pending) that have breached their SLA resolution target."
)
def get_overdue_incidents(
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
):
    items, _ = IncidentService.list_incidents(
        db=db,
        is_overdue_filter=True,
        page=1,
        page_size=200,
    )
    # Filter to only active ones
    active_overdue = [i for i in items if i.status not in ("Resolved", "Closed")]
    return active_overdue

@router.get(
    "/{incident_id}",
    response_model=IncidentDetailResponse,
    summary="Retrieve incident details",
    description="Fetches complete incident information including calculated SLA age, investigation notes, and full activity history. Supports ID or incident_number."
)
def get_incident(
    incident_id: str = Path(..., description="Internal numeric ID or business incident number (e.g., INC-2026-0001)"),
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
):
    return IncidentService.get_incident_detail(db, incident_id)

@router.patch(
    "/{incident_id}",
    response_model=IncidentResponse,
    summary="Update incident attributes",
    description="Updates incident metadata like assignee, priority, severity, category, or service. Records change in audit log."
)
def update_incident(
    payload: IncidentUpdate,
    incident_id: str = Path(..., description="Internal numeric ID or incident number"),
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_role([UserRole.ADMIN, UserRole.ENGINEER])),
):
    return IncidentService.update_incident(db, incident_id, payload, performed_by=user.username)

@router.post(
    "/{incident_id}/status",
    response_model=IncidentResponse,
    summary="Transition incident status",
    description="Enforces strict ITIL status lifecycle transitions (Open -> In Progress -> Pending/Resolved -> Closed). Reopening closed incidents requires Admin role."
)
def transition_incident_status(
    payload: StatusTransitionRequest,
    incident_id: str = Path(..., description="Internal numeric ID or incident number"),
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_role([UserRole.ADMIN, UserRole.ENGINEER])),
):
    return IncidentService.transition_status(
        db=db,
        identifier=incident_id,
        payload=payload,
        performed_by=user.username,
        user_role=user.role,
    )
