"""Solenoid status model for persistent state tracking."""
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from app.config.database import Base


class SolenoidStatus(Base):
    """Model for tracking solenoid valve states."""
    __tablename__ = 'solenoid_status'

    solenoid_name = Column(String(100), primary_key=True, index=True)
    is_open = Column(Integer, nullable=False, default=0)  # 0 = closed, 1 = open
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self):
        status = "open" if self.is_open else "closed"
        return f"<SolenoidStatus(name={self.solenoid_name}, status={status}, updated={self.last_updated})>"

