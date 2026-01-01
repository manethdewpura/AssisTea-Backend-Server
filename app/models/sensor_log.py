"""Sensor log model for storing sensor readings."""
from sqlalchemy import Column, Integer, String, Float, DateTime, Enum
from sqlalchemy.sql import func
from app.config.database import Base
import enum


class SensorType(enum.Enum):
    """Sensor type enumeration."""
    PRESSURE = "pressure"
    SOIL_MOISTURE = "soil_moisture"
    TANK_LEVEL = "tank_level"
    SLOPE = "slope"
    ALTITUDE = "altitude"
    WEATHER = "weather"


class SensorLog(Base):
    """Model for storing sensor readings."""
    __tablename__ = 'sensor_logs'

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    sensor_type = Column(Enum(SensorType), nullable=False, index=True)
    zone_id = Column(Integer, nullable=True, index=True)  # None for system-wide sensors
    value = Column(Float, nullable=False)  # Processed/standardized value
    unit = Column(String(20), nullable=False)  # Standardized unit (e.g., 'kPa', '%', 'cm')
    raw_value = Column(Float, nullable=True)  # Original raw reading
    raw_unit = Column(String(20), nullable=True)  # Original unit

    def __repr__(self):
        return f"<SensorLog(id={self.id}, type={self.sensor_type.value}, zone={self.zone_id}, value={self.value} {self.unit})>"

