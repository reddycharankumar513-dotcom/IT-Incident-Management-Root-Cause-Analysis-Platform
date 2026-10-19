from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, model_validator, ConfigDict
from app.schemas.common import SeverityEnum, PriorityEnum, ImpactEnum, UrgencyEnum, IncidentStatusEnum
from app.schemas.note import InvestigationNoteResponse
from app.schemas.activity import IncidentActivityResponse

class IncidentCreate(BaseModel):
    title: str = Field(min_length=3, max_length=255, description="Clear, concise summary of the incident")
    description: str = Field(min_length=5, max_length=10000, description="Detailed diagnostic information, errors, affected scope")
    category: str = Field(default="Software", min_length=2, max_length=64, description="Category (e.g., Software, Hardware, Network, Database, Security, Infrastructure)")
    subcategory: Optional[str] = Field(default=None, max_length=64, description="Subcategory or component")
    severity: SeverityEnum = Field(default=SeverityEnum.MEDIUM, description="Incident severity level")
    priority: Optional[PriorityEnum] = Field(default=None, description="P1-P4 priority; if not provided, automatically derived from severity")
    impact: ImpactEnum = Field(default=ImpactEnum.MEDIUM, description="Impact on business operations")
    urgency: UrgencyEnum = Field(default=UrgencyEnum.MEDIUM, description="Urgency to restore service")
    reporter: str = Field(min_length=2, max_length=128, description="User or automated system reporting the issue")
    assignee: Optional[str] = Field(default=None, max_length=128, description="Assigned engineer or primary responder")
    assignment_group: Optional[str] = Field(default=None, max_length=128, description="Team or group responsible for resolution")
    service: str = Field(min_length=2, max_length=128, description="Affected business or technical service (e.g. Payment Gateway, Auth API)")
    sla_resolution_target_hours: Optional[float] = Field(default=None, ge=0.1, le=720.0, description="Optional custom SLA resolution target in hours")
    sla_response_target_hours: Optional[float] = Field(default=None, ge=0.01, le=72.0, description="Optional custom SLA response target in hours")

class IncidentUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=3, max_length=255)
    description: Optional[str] = Field(default=None, min_length=5, max_length=10000)
    category: Optional[str] = Field(default=None, min_length=2, max_length=64)
    subcategory: Optional[str] = Field(default=None, max_length=64)
    severity: Optional[SeverityEnum] = None
    priority: Optional[PriorityEnum] = None
    impact: Optional[ImpactEnum] = None
    urgency: Optional[UrgencyEnum] = None
    assignee: Optional[str] = Field(default=None, max_length=128)
    assignment_group: Optional[str] = Field(default=None, max_length=128)
    service: Optional[str] = Field(default=None, min_length=2, max_length=128)
    sla_resolution_target_hours: Optional[float] = Field(default=None, ge=0.1, le=720.0)

class StatusTransitionRequest(BaseModel):
    status: IncidentStatusEnum = Field(description="Target status: Open, In Progress, Pending, Resolved, Closed")
    reason: Optional[str] = Field(default=None, max_length=1000, description="Reason for status change")
    pending_reason: Optional[str] = Field(default=None, max_length=255, description="Required when setting status to Pending (e.g., Awaiting Vendor, Awaiting User Info)")
    root_cause: Optional[str] = Field(default=None, max_length=5000, description="RCA Root Cause description (required/encouraged when resolving)")
    corrective_action: Optional[str] = Field(default=None, max_length=5000, description="RCA Corrective Action taken")
    preventive_action: Optional[str] = Field(default=None, max_length=5000, description="RCA Preventive Action plan")
    resolution_summary: Optional[str] = Field(default=None, max_length=5000, description="Resolution details (required when resolving)")

    @model_validator(mode="after")
    def validate_transition_fields(self):
        if self.status == IncidentStatusEnum.PENDING and not self.pending_reason:
            raise ValueError("pending_reason is required when transitioning status to 'Pending'")
        if self.status == IncidentStatusEnum.RESOLVED and not self.resolution_summary:
            raise ValueError("resolution_summary is required when transitioning status to 'Resolved'")
        return self

class IncidentResponse(BaseModel):
    id: int
    incident_number: str
    title: str
    description: str
    category: str
    subcategory: Optional[str] = None
    severity: str
    priority: str
    impact: str
    urgency: str
    status: str
    pending_reason: Optional[str] = None
    service: str
    reporter: str
    assignee: Optional[str] = None
    assignment_group: Optional[str] = None
    
    # RCA fields
    root_cause: Optional[str] = None
    corrective_action: Optional[str] = None
    preventive_action: Optional[str] = None
    resolution_summary: Optional[str] = None

    # SLA parameters
    sla_resolution_target_hours: float
    sla_response_target_hours: float

    # Timestamps
    created_at: datetime
    updated_at: datetime
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None

    # Dynamically Computed SLA & Operational Metrics
    age_hours: float
    age_human_readable: str
    time_to_resolve_hours: Optional[float] = None
    time_to_acknowledge_hours: Optional[float] = None
    sla_deadline: Optional[datetime] = None
    is_overdue: bool
    sla_status: str

    model_config = ConfigDict(from_attributes=True)

class IncidentDetailResponse(IncidentResponse):
    notes: List[InvestigationNoteResponse] = []
    activities: List[IncidentActivityResponse] = []
