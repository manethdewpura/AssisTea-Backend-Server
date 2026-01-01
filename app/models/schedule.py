"""Schedule models for irrigation and fertigation schedules."""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Time
from sqlalchemy.sql import func
from app.config.database import Base
import enum


class DayOfWeek(enum.Enum):
    """Day of week enumeration."""
    MONDAY = 0
    TUESDAY = 1
    WEDNESDAY = 2
    THURSDAY = 3
    FRIDAY = 4
    SATURDAY = 5
    SUNDAY = 6


class IrrigationSchedule(Base):
    """Model for irrigation schedules."""
    __tablename__ = 'irrigation_schedules'

    id = Column(Integer, primary_key=True, index=True)
    zone_id = Column(Integer, nullable=False, index=True)
    day_of_week = Column(Integer, nullable=False)  # 0-6 (Monday-Sunday)
    time = Column(Time, nullable=False)  # Scheduled time
    enabled = Column(Boolean, default=True, nullable=False, index=True)
    last_run = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self):
        return f"<IrrigationSchedule(id={self.id}, zone={self.zone_id}, day={self.day_of_week}, time={self.time}, enabled={self.enabled})>"


class FertigationSchedule(Base):
    """Model for fertigation schedules."""
    __tablename__ = 'fertigation_schedules'

    id = Column(Integer, primary_key=True, index=True)
    zone_id = Column(Integer, nullable=False, index=True)
    day_of_week = Column(Integer, nullable=False)  # 0-6 (Monday-Sunday)
    time = Column(Time, nullable=False)  # Scheduled time
    enabled = Column(Boolean, default=True, nullable=False, index=True)
    last_run = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self):
        return f"<FertigationSchedule(id={self.id}, zone={self.zone_id}, day={self.day_of_week}, time={self.time}, enabled={self.enabled})>"

