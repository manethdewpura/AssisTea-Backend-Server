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
    valve_gpio_pin = Column(Integer, nullable=False)  # GPIO pin for zone valve control (zone-specific)
    soil_moisture_sensor_channel = Column(Integer, nullable=True)  # ADS1115 channel for soil moisture sensor (zone-specific)
    enabled = Column(String(10), default='true', nullable=False)  # 'true' or 'false' as string
    
    # Note: Pumps and pressure sensors are system-wide and configured in config.py
    # - Irrigation pump: GPIO 23
    # - Fertilizer pump: GPIO 22
    # - Irrigation pump pressure: ADS1115 channel 2 (A2)
    # - Fertilizer pump pressure: ADS1115 channel 3 (A3)

    def __repr__(self):
        return f"<ZoneConfig(zone_id={self.zone_id}, name={self.name}, altitude={self.altitude}m, slope={self.slope}°)>"

