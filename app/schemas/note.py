from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
from app.schemas.common import NoteTypeEnum

class InvestigationNoteCreate(BaseModel):
    note_type: NoteTypeEnum = Field(default=NoteTypeEnum.INVESTIGATION, description="Type of note (Observation, Hypothesis, Investigation, Action, Workaround, Evidence)")
    content: str = Field(min_length=3, max_length=5000, description="Detailed notes, logs, diagnostic observations, or hypotheses")
    author: Optional[str] = Field(default=None, max_length=128, description="Author identifier or username (defaults to authenticated user)")

class InvestigationNoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    incident_id: int
    note_type: str
    author: str
    content: str
    created_at: datetime
