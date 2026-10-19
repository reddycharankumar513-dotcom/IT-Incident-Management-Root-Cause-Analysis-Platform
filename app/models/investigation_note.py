from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class InvestigationNote(Base):
    __tablename__ = "investigation_notes"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    incident_id = Column(Integer, ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True)
    note_type = Column(String(32), nullable=False, default="Investigation")  # Observation, Hypothesis, Action, Workaround, Evidence
    author = Column(String(128), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    incident = relationship("Incident", back_populates="notes")

    def __repr__(self):
        return f"<InvestigationNote(id={self.id}, incident_id={self.incident_id}, type={self.note_type}, author={self.author})>"
