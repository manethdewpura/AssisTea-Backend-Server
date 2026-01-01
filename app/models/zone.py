"""Zone configuration model."""
from sqlalchemy import Column, Integer, String, Float
from app.config.database import Base


class ZoneConfig(Base):
    """Model for zone configuration."""
    __tablename__ = 'zone_configs'

    zone_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)  # Zone name/description
    altitude = Column(Float, nullable=False)  # Altitude in meters above sea level
    slope = Column(Float, nullable=False)  # Slope angle in degrees
    area = Column(Float, nullable=False)  # Area in square meters
    base_pressure = Column(Float, nullable=False)  # Base pressure requirement in kPa
    valve_gpio_pin = Column(Integer, nullable=False)  # GPIO pin for zone valve control
    pump_gpio_pin = Column(Integer, nullable=True)  # GPIO pin for pump control (if zone-specific)
    soil_moisture_sensor_pin = Column(Integer, nullable=True)  # GPIO pin for soil moisture sensor
    pressure_sensor_pin = Column(Integer, nullable=True)  # GPIO pin for pressure sensor
    enabled = Column(String(10), default='true', nullable=False)  # 'true' or 'false' as string

    def __repr__(self):
        return f"<ZoneConfig(zone_id={self.zone_id}, name={self.name}, altitude={self.altitude}m, slope={self.slope}°)>"

