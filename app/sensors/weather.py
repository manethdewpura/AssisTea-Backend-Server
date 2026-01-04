"""Weather data reader from WeatherCurrent model."""
from typing import Dict, Any, Optional
from datetime import datetime
from flask import current_app
from app.sensors.base import BaseSensor
from app.models.weather_records import WeatherCurrent


class WeatherReader(BaseSensor):
    """Interface to read weather data from WeatherCurrent model."""

    def __init__(self, sensor_id: str = "weather_reader", app=None):
        """
        Initialize weather reader.
        
        Args:
            sensor_id: Unique sensor identifier
            app: Flask app instance (optional, will use current_app if not provided)
        """
        super().__init__(sensor_id, zone_id=None)  # Weather is system-wide
        self.app = app

    def _get_latest_weather(self) -> Optional[Dict[str, Any]]:
        """
        Get latest weather data from WeatherCurrent model.
        
        Returns:
            Dictionary with weather data or None if not available
        """
        try:
            # Use app context to query database
            if self.app:
                app_context = self.app.app_context()
            else:
                try:
                    app_context = current_app.app_context()
                except RuntimeError:
                    # Not in a request context, return None
                    self.mark_failure()
                    return None
            
            with app_context:
                # Get the most recent weather record (prefer non-ML generated, but allow ML if needed)
                # Order by measured_at (actual weather time) descending, then by synced_at
                # Use a more compatible approach for handling NULL values
                from sqlalchemy import case
                weather_record = WeatherCurrent.query.order_by(
                    case((WeatherCurrent.measured_at.is_(None), 1), else_=0),
                    WeatherCurrent.measured_at.desc(),
                    WeatherCurrent.synced_at.desc()
                ).first()
                
                if weather_record:
                    # Map WeatherCurrent fields to expected format
                    weather_data = {
                        'condition': self._map_weather_condition(weather_record.weather_main),
                        'temperature': weather_record.temp,
                        'humidity': weather_record.humidity,
                        'precipitation': (weather_record.rain_1h or 0.0) + (weather_record.rain_3h or 0.0),
                        'pressure': weather_record.pressure,
                        'wind_speed': weather_record.wind_speed,
                        'wind_deg': weather_record.wind_deg,
                        'clouds': weather_record.clouds_all,
                        'weather_main': weather_record.weather_main,
                        'weather_description': weather_record.weather_description,
                        'measured_at': weather_record.measured_at,
                        'is_ml_generated': weather_record.is_ml_generated,
                        'confidence_score': weather_record.confidence_score
                    }
                    self.mark_success()
                    return weather_data
            
            self.mark_success()
            return None
        except Exception as e:
            self.mark_failure()
            raise Exception(f"Failed to read weather data: {str(e)}")
    
    def _map_weather_condition(self, weather_main: Optional[str]) -> str:
        """
        Map OpenWeatherMap weather main condition to standardized condition.
        
        Args:
            weather_main: Weather main condition from API (e.g., 'Clear', 'Rain', 'Clouds')
            
        Returns:
            Standardized condition: 'clear', 'cloudy', or 'rainy'
        """
        if not weather_main:
            return 'clear'
        
        weather_main_lower = weather_main.lower()
        
        # Clear conditions
        if weather_main_lower in ['clear', 'sunny']:
            return 'clear'
        
        # Rainy conditions
        if weather_main_lower in ['rain', 'drizzle', 'thunderstorm', 'snow']:
            return 'rainy'
        
        # Cloudy conditions
        if weather_main_lower in ['clouds', 'mist', 'fog', 'haze', 'dust', 'sand', 'ash', 'squall', 'tornado']:
            return 'cloudy'
        
        # Default to clear
        return 'clear'

    def read_raw(self) -> Dict[str, Any]:
        """
        Read raw weather data from database.
        
        Returns:
            Dictionary with weather data
        """
        weather_data = self._get_latest_weather()
        
        if weather_data is None:
            # Return default clear weather if no data available
            return {
                'condition': 'clear',
                'temperature': 25.0,
                'humidity': 50.0,
                'precipitation': 0.0,
                'unit': 'weather'
            }
        
        return weather_data

    def read_standardized(self) -> Dict[str, Any]:
        """
        Read and return standardized weather data.
        
        Returns:
            Dictionary with standardized weather reading
        """
        raw_data = self.read_raw()
        
        # Extract and standardize weather condition (already mapped in _get_latest_weather)
        condition = raw_data.get('condition', 'clear')
        
        # Ensure condition is lowercase
        if isinstance(condition, str):
            condition = condition.lower()
        
        reading = {
            'condition': condition,
            'temperature': raw_data.get('temperature', 25.0),
            'temperature_unit': 'celsius',
            'humidity': raw_data.get('humidity', 50.0),
            'humidity_unit': '%',
            'precipitation': raw_data.get('precipitation', 0.0),
            'precipitation_unit': 'mm',
            'pressure': raw_data.get('pressure'),
            'wind_speed': raw_data.get('wind_speed'),
            'wind_deg': raw_data.get('wind_deg'),
            'clouds': raw_data.get('clouds'),
            'timestamp': datetime.now(),
            'sensor_id': self.sensor_id,
            'zone_id': self.zone_id,
            'is_ml_generated': raw_data.get('is_ml_generated', False),
            'confidence_score': raw_data.get('confidence_score', 1.0)
        }
        
        self.last_reading = reading
        self.last_reading_time = datetime.now()
        
        return reading

    def is_weather_clear(self) -> bool:
        """
        Check if weather is clear (suitable for irrigation).
        
        Returns:
            True if weather is clear, False otherwise
        """
        reading = self.read_standardized()
        return reading['condition'] == 'clear' and reading['precipitation'] == 0.0

