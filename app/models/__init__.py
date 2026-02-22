"""Database models package."""
from app.models.sensor_log import SensorLog
from app.models.operational_log import OperationalLog
from app.models.system_log import SystemLog
from app.models.schedule import IrrigationSchedule, FertigationSchedule
from app.models.zone import ZoneConfig
from app.models.system_config import SystemConfig
from app.models.weather_records import WeatherCurrent, WeatherForecast
from app.models.solenoid_status import SolenoidStatus

__all__ = [
    'SensorLog',
    'OperationalLog',
    'SystemLog',
    'IrrigationSchedule',
    'FertigationSchedule',
    'ZoneConfig',
    'SystemConfig',
    'WeatherCurrent',
    'WeatherForecast',
    'SolenoidStatus'
]

