"""Operational log model for storing irrigation/fertigation operations."""
from sqlalchemy import Column, Integer, String, Float, DateTime, Enum
from sqlalchemy.sql import func
from app.config.database import Base
import enum


class OperationType(enum.Enum):
    """Operation type enumeration."""
    IRRIGATION = "irrigation"
    FERTIGATION = "fertigation"


class OperationStatus(enum.Enum):
    """Operation status enumeration."""
    STARTED = "started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    STOPPED = "stopped"
    FAILED = "failed"
    SKIPPED = "skipped"


class OperationalLog(Base):
    """Model for storing operational data."""
    __tablename__ = 'operational_logs'

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    operation_type = Column(Enum(OperationType), nullable=False, index=True)
    zone_id = Column(Integer, nullable=False, index=True)
    status = Column(Enum(OperationStatus), nullable=False, index=True)
    duration = Column(Float, nullable=True)  # Duration in seconds
    pressure = Column(Float, nullable=True)  # Average pressure during operation (kPa)
    flow_rate = Column(Float, nullable=True)  # Flow rate (L/min)
    water_volume = Column(Float, nullable=True)  # Total water volume (L)
    fertilizer_volume = Column(Float, nullable=True)  # Total fertilizer volume (L) - for fertigation
    start_moisture = Column(Float, nullable=True)  # Soil moisture at start (%)
    end_moisture = Column(Float, nullable=True)  # Soil moisture at end (%)
    notes = Column(String(500), nullable=True)  # Additional notes

    def __repr__(self):
        return f"<OperationalLog(id={self.id}, type={self.operation_type.value}, zone={self.zone_id}, status={self.status.value})>"

