"""Sensor interfaces package."""
from app.sensors.base import BaseSensor
from app.sensors.pressure import PressureSensor
from app.sensors.soil_moisture import SoilMoistureSensor
from app.sensors.tank_level import TankLevelSensor
from app.sensors.slope_altitude import SlopeAltitudeSensor
from app.sensors.weather import WeatherReader

__all__ = [
    'BaseSensor',
    'PressureSensor',
    'SoilMoistureSensor',
    'TankLevelSensor',
    'SlopeAltitudeSensor',
    'WeatherReader',
]

