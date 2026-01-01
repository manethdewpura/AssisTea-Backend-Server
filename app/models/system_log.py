"""System log model for storing system events and errors."""
from sqlalchemy import Column, Integer, String, DateTime, Enum
from sqlalchemy.sql import func
from app.config.database import Base
import enum


class LogLevel(enum.Enum):
    """Log level enumeration."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class SystemLog(Base):
    """Model for storing system logs."""
    __tablename__ = 'system_logs'

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    log_level = Column(Enum(LogLevel), nullable=False, index=True)
    component = Column(String(50), nullable=False, index=True)  # Component name (e.g., 'sensor', 'controller', 'pump')
    message = Column(String(1000), nullable=False)
    error_code = Column(String(20), nullable=True, index=True)  # Error code if applicable
    zone_id = Column(Integer, nullable=True, index=True)  # Zone ID if applicable
    sensor_id = Column(String(50), nullable=True)  # Sensor identifier if applicable

    def __repr__(self):
        return f"<SystemLog(id={self.id}, level={self.log_level.value}, component={self.component}, message={self.message[:50]}...)>"

