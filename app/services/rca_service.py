from datetime import datetime
from typing import List
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.incident import Incident
from app.models.investigation_note import InvestigationNote
from app.models.activity import IncidentActivity
from app.schemas.rca import RcaUpdateRequest, RcaResponse
from app.schemas.note import InvestigationNoteCreate, InvestigationNoteResponse
from app.schemas.activity import IncidentActivityResponse
from app.services.incident_service import IncidentService
from app.utils.timezone import utc_now
from app.logging_config import logger

class RcaService:
    @classmethod
    def update_rca(
        cls,
        db: Session,
        identifier: str,
        payload: RcaUpdateRequest,
        performed_by: str,
    ) -> RcaResponse:
        incident = IncidentService.get_incident_by_identifier(db, identifier)
        now = utc_now()

        # Update RCA fields
        incident.root_cause = payload.root_cause
        incident.corrective_action = payload.corrective_action
        if payload.preventive_action is not None:
            incident.preventive_action = payload.preventive_action
        if payload.resolution_summary is not None:
            incident.resolution_summary = payload.resolution_summary
        
        incident.updated_at = now

        # Record activity
        activity = IncidentActivity(
            incident_id=incident.id,
            action="RCA_UPDATED",
            field_name="root_cause",
            old_value=None,
            new_value=payload.root_cause[:100] + "..." if len(payload.root_cause) > 100 else payload.root_cause,
            performed_by=performed_by,
            notes="Root cause analysis details and corrective actions updated",
            timestamp=now
        )
        db.add(activity)

        db.commit()
        db.refresh(incident)
        logger.info(f"Updated RCA for incident {incident.incident_number} by {performed_by}")

        return RcaResponse(
            incident_id=incident.id,
            incident_number=incident.incident_number,
            root_cause=incident.root_cause,
            corrective_action=incident.corrective_action,
            preventive_action=incident.preventive_action,
            resolution_summary=incident.resolution_summary,
            resolved_at=incident.resolved_at,
            closed_at=incident.closed_at,
            updated_at=incident.updated_at
        )

    @classmethod
    def add_investigation_note(
        cls,
        db: Session,
        identifier: str,
        payload: InvestigationNoteCreate,
        performed_by: str,
    ) -> InvestigationNoteResponse:
        incident = IncidentService.get_incident_by_identifier(db, identifier)
        now = utc_now()

        author = payload.author or performed_by

        note = InvestigationNote(
            incident_id=incident.id,
            note_type=payload.note_type.value,
            author=author,
            content=payload.content,
            created_at=now,
        )
        db.add(note)
        db.flush()

        # Record activity
        activity = IncidentActivity(
            incident_id=incident.id,
            action="NOTE_ADDED",
            field_name="notes",
            old_value=None,
            new_value=f"[{payload.note_type.value}] {payload.content[:80]}...",
            performed_by=performed_by,
            notes=f"Investigation note added by {author}",
            timestamp=now
        )
        db.add(activity)

        incident.updated_at = now
        db.commit()
        db.refresh(note)
        logger.info(f"Added investigation note to incident {incident.incident_number} by {author}")

        return InvestigationNoteResponse.model_validate(note)

    @classmethod
    def list_notes(cls, db: Session, identifier: str) -> List[InvestigationNoteResponse]:
        incident = IncidentService.get_incident_by_identifier(db, identifier)
        return [InvestigationNoteResponse.model_validate(n) for n in incident.notes]

    @classmethod
    def list_activities(cls, db: Session, identifier: str) -> List[IncidentActivityResponse]:
        incident = IncidentService.get_incident_by_identifier(db, identifier)
        return [IncidentActivityResponse.model_validate(a) for a in incident.activities]
