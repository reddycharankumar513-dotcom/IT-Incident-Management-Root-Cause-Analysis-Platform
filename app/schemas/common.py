from enum import Enum
from typing import Optional, Generic, TypeVar, List
from pydantic import BaseModel, Field

class SeverityEnum(str, Enum):
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"

class PriorityEnum(str, Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"

class ImpactEnum(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"

class UrgencyEnum(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"

class IncidentStatusEnum(str, Enum):
    OPEN = "Open"
    IN_PROGRESS = "In Progress"
    PENDING = "Pending"
    RESOLVED = "Resolved"
    CLOSED = "Closed"

class NoteTypeEnum(str, Enum):
    OBSERVATION = "Observation"
    HYPOTHESIS = "Hypothesis"
    INVESTIGATION = "Investigation"
    ACTION = "Action"
    WORKAROUND = "Workaround"
    EVIDENCE = "Evidence"

class UserRole(str, Enum):
    ADMIN = "Admin"
    ENGINEER = "Engineer"
    VIEWER = "Viewer"

class HealthCheck(BaseModel):
    status: str = "healthy"
    app_name: str
    environment: str
    timestamp: str

T = TypeVar("T")

class PaginatedResponse(BaseModel, Generic[T]):
    total: int
    page: int
    page_size: int
    items: List[T]
