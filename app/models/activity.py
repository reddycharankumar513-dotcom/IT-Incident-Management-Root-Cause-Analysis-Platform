from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class IncidentActivity(Base):
    __tablename__ = "incident_activities"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    incident_id = Column(Integer, ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True)
    action = Column(String(64), nullable=False)  # CREATED, STATUS_CHANGED, ASSIGNED, SEVERITY_CHANGED, RCA_UPDATED, NOTE_ADDED, RESOLVED, CLOSED, REOPENED
    field_name = Column(String(64), nullable=True)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    performed_by = Column(String(128), nullable=False)
    notes = Column(Text, nullable=True)
    timestamp = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)

    incident = relationship("Incident", back_populates="activities")

    def __repr__(self):
        return f"<IncidentActivity(id={self.id}, incident_id={self.incident_id}, action={self.action}, by={self.performed_by})>"
