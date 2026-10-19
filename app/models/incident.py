from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Float, DateTime
from sqlalchemy.orm import relationship
from app.database import Base

class Incident(Base):
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    incident_number = Column(String(32), unique=True, nullable=False, index=True)
    title = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=False)
    
    # Classification
    category = Column(String(64), nullable=False, index=True)
    subcategory = Column(String(64), nullable=True)
    severity = Column(String(16), nullable=False, default="Medium", index=True)  # Critical, High, Medium, Low
    priority = Column(String(16), nullable=False, default="P3", index=True)      # P1, P2, P3, P4
    impact = Column(String(16), nullable=False, default="Medium")               # High, Medium, Low
    urgency = Column(String(16), nullable=False, default="Medium")              # High, Medium, Low
    
    # Lifecycle & Ownership
    status = Column(String(32), nullable=False, default="Open", index=True)     # Open, In Progress, Pending, Resolved, Closed
    pending_reason = Column(String(255), nullable=True)
    service = Column(String(128), nullable=False, index=True)
    reporter = Column(String(128), nullable=False, index=True)
    assignee = Column(String(128), nullable=True, index=True)
    assignment_group = Column(String(128), nullable=True, index=True)

    # Root Cause Analysis (RCA) & Resolution
    root_cause = Column(Text, nullable=True)
    corrective_action = Column(Text, nullable=True)
    preventive_action = Column(Text, nullable=True)
    resolution_summary = Column(Text, nullable=True)

    # SLA tracking configuration
    sla_resolution_target_hours = Column(Float, nullable=False, default=24.0)
    sla_response_target_hours = Column(Float, nullable=False, default=2.0)

    # Timestamps (Stored in UTC)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    acknowledged_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)

    # Relationships
    notes = relationship(
        "InvestigationNote",
        back_populates="incident",
        cascade="all, delete-orphan",
        order_by="InvestigationNote.created_at.asc()"
    )
    activities = relationship(
        "IncidentActivity",
        back_populates="incident",
        cascade="all, delete-orphan",
        order_by="IncidentActivity.timestamp.asc()"
    )

    def __repr__(self):
        return f"<Incident(id={self.id}, number={self.incident_number}, status={self.status}, severity={self.severity})>"
