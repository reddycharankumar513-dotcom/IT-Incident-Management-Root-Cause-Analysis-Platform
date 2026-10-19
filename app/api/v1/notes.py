from typing import List
from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.note import InvestigationNoteCreate, InvestigationNoteResponse
from app.schemas.common import UserRole
from app.services.rca_service import RcaService
from app.security import get_current_user, require_role, AuthenticatedUser

router = APIRouter(prefix="/incidents/{incident_id}/notes", tags=["Investigation Notes"])

@router.post(
    "",
    response_model=InvestigationNoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add an investigation note",
    description="Records diagnostic observations, investigative hypotheses, actions taken, workarounds, or log evidence."
)
def add_note(
    payload: InvestigationNoteCreate,
    incident_id: str = Path(..., description="Internal numeric ID or incident number"),
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_role([UserRole.ADMIN, UserRole.ENGINEER])),
):
    return RcaService.add_investigation_note(
        db=db,
        identifier=incident_id,
        payload=payload,
        performed_by=user.username,
    )

@router.get(
    "",
    response_model=List[InvestigationNoteResponse],
    summary="List investigation notes",
    description="Returns chronological investigation notes recorded for this incident."
)
def list_notes(
    incident_id: str = Path(..., description="Internal numeric ID or incident number"),
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
):
    return RcaService.list_notes(db=db, identifier=incident_id)
