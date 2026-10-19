from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict

class IncidentActivityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    incident_id: int
    action: str
    field_name: Optional[str] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    performed_by: str
    notes: Optional[str] = None
    timestamp: datetime
