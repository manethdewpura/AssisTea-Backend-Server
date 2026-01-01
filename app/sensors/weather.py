"""Weather data reader from existing SQLite database."""
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import sqlite3
import os
from app.sensors.base import BaseSensor
from app.config.config import WEATHER_DB_PATH


class WeatherReader(BaseSensor):
    """Interface to read weather data from existing SQLite database."""

    def __init__(self, sensor_id: str = "weather_reader"):
        """
        Initialize weather reader.
        
        Args:
            sensor_id: Unique sensor identifier
        """
        super().__init__(sensor_id, zone_id=None)  # Weather is system-wide
        self.db_path = WEATHER_DB_PATH

    def _get_db_connection(self):
        """Get database connection."""
        if not os.path.exists(self.db_path):
            raise FileNotFoundError(f"Weather database not found at {self.db_path}")
        return sqlite3.connect(self.db_path)

    def _get_latest_weather(self) -> Optional[Dict[str, Any]]:
        """
        Get latest weather data from database.
        
        Returns:
            Dictionary with weather data or None if not available
        """
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            
            # Try to get latest weather record
            # Assuming table name is 'weather' with columns: timestamp, condition, temperature, humidity, etc.
            # Adjust query based on actual schema
            cursor.execute("""
                SELECT * FROM weather 
                ORDER BY timestamp DESC 
                LIMIT 1
            """)
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                # Get column names
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(weather)")
                columns = [col[1] for col in cursor.fetchall()]
                conn.close()
                
                # Create dictionary
                weather_data = dict(zip(columns, row))
                self.mark_success()
                return weather_data
            
            self.mark_success()
            return None
        except Exception as e:
            self.mark_failure()
            raise Exception(f"Failed to read weather data: {str(e)}")

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
        
        # Extract and standardize weather condition
        condition = raw_data.get('condition', 'clear').lower()
        
        # Normalize condition values
        if condition in ['sunny', 'clear', 'fair']:
            standardized_condition = 'clear'
        elif condition in ['cloudy', 'overcast']:
            standardized_condition = 'cloudy'
        elif condition in ['rain', 'rainy', 'precipitation']:
            standardized_condition = 'rainy'
        else:
            standardized_condition = 'clear'  # Default to clear
        
        reading = {
            'condition': standardized_condition,
            'temperature': raw_data.get('temperature', 25.0),
            'temperature_unit': 'celsius',
            'humidity': raw_data.get('humidity', 50.0),
            'humidity_unit': '%',
            'precipitation': raw_data.get('precipitation', 0.0),
            'precipitation_unit': 'mm',
            'timestamp': datetime.now(),
            'sensor_id': self.sensor_id,
            'zone_id': self.zone_id
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

