from typing import List
from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.rca import RcaUpdateRequest, RcaResponse
from app.schemas.activity import IncidentActivityResponse
from app.schemas.common import UserRole
from app.services.rca_service import RcaService
from app.security import get_current_user, require_role, AuthenticatedUser

router = APIRouter(prefix="/incidents/{incident_id}", tags=["Root Cause Analysis (RCA) & Audit"])

@router.put(
    "/rca",
    response_model=RcaResponse,
    summary="Record or update Root Cause Analysis (RCA)",
    description="Documents the confirmed root cause, corrective actions taken, and systemic preventive measures."
)
def update_rca(
    payload: RcaUpdateRequest,
    incident_id: str = Path(..., description="Internal numeric ID or incident number"),
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_role([UserRole.ADMIN, UserRole.ENGINEER])),
):
    return RcaService.update_rca(
        db=db,
        identifier=incident_id,
        payload=payload,
        performed_by=user.username,
    )

@router.get(
    "/activities",
    response_model=List[IncidentActivityResponse],
    summary="Get incident activity history and audit trail",
    description="Retrieves a complete chronological audit log of all changes, transitions, reassignments, and notes for this incident."
)
def list_activities(
    incident_id: str = Path(..., description="Internal numeric ID or incident number"),
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
):
    return RcaService.list_activities(db=db, identifier=incident_id)
