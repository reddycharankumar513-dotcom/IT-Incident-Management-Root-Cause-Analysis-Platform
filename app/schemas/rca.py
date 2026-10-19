from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict

class RcaUpdateRequest(BaseModel):
    root_cause: str = Field(min_length=5, max_length=5000, description="Underlying technical or systemic root cause identified")
    corrective_action: str = Field(min_length=5, max_length=5000, description="Immediate corrective action taken to restore service")
    preventive_action: Optional[str] = Field(default=None, max_length=5000, description="Long-term systemic fix or guardrail to prevent recurrence")
    resolution_summary: Optional[str] = Field(default=None, max_length=5000, description="Executive resolution summary for stakeholders")

class RcaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    incident_id: int
    incident_number: str
    root_cause: Optional[str] = None
    corrective_action: Optional[str] = None
    preventive_action: Optional[str] = None
    resolution_summary: Optional[str] = None
    resolved_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    updated_at: datetime
