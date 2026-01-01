"""Data validation utilities for sensor readings."""
from typing import Optional, Tuple
from app.config.config import (
    MIN_SOIL_MOISTURE_PERCENT, MAX_SOIL_MOISTURE_PERCENT,
    MIN_PRESSURE_KPA, MAX_PRESSURE_KPA,
    TANK_EMPTY_LEVEL_CM, TANK_FULL_LEVEL_CM,
    ABNORMAL_READING_THRESHOLD
)
import statistics


class DataValidator:
    """Validate sensor readings within expected ranges."""

    def __init__(self):
        """Initialize validator."""
        self.reading_history: dict = {}  # sensor_id -> list of recent readings

    def validate_soil_moisture(self, value: float, sensor_id: str) -> Tuple[bool, Optional[str]]:
        """
        Validate soil moisture reading.
        
        Args:
            value: Soil moisture percentage (0-100)
            sensor_id: Sensor identifier
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if value < MIN_SOIL_MOISTURE_PERCENT or value > MAX_SOIL_MOISTURE_PERCENT:
            return False, f"Soil moisture {value}% outside valid range [{MIN_SOIL_MOISTURE_PERCENT}, {MAX_SOIL_MOISTURE_PERCENT}]%"
        
        # Check for abnormal readings compared to history
        if sensor_id in self.reading_history:
            history = self.reading_history[sensor_id]
            if len(history) >= 5:
                mean = statistics.mean(history)
                stdev = statistics.stdev(history) if len(history) > 1 else 0
                
                if stdev > 0:
                    z_score = abs(value - mean) / stdev
                    if z_score > ABNORMAL_READING_THRESHOLD:
                        return False, f"Abnormal soil moisture reading: {value}% (z-score: {z_score:.2f})"
        
        # Update history
        if sensor_id not in self.reading_history:
            self.reading_history[sensor_id] = []
        self.reading_history[sensor_id].append(value)
        if len(self.reading_history[sensor_id]) > 20:  # Keep last 20 readings
            self.reading_history[sensor_id].pop(0)
        
        return True, None

    def validate_pressure(self, value: float, sensor_id: str) -> Tuple[bool, Optional[str]]:
        """
        Validate pressure reading.
        
        Args:
            value: Pressure in kPa
            sensor_id: Sensor identifier
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if value < MIN_PRESSURE_KPA or value > MAX_PRESSURE_KPA:
            return False, f"Pressure {value} kPa outside valid range [{MIN_PRESSURE_KPA}, {MAX_PRESSURE_KPA}] kPa"
        
        # Check for abnormal readings
        if sensor_id in self.reading_history:
            history = self.reading_history[sensor_id]
            if len(history) >= 5:
                mean = statistics.mean(history)
                stdev = statistics.stdev(history) if len(history) > 1 else 0
                
                if stdev > 0:
                    z_score = abs(value - mean) / stdev
                    if z_score > ABNORMAL_READING_THRESHOLD:
                        return False, f"Abnormal pressure reading: {value} kPa (z-score: {z_score:.2f})"
        
        # Update history
        if sensor_id not in self.reading_history:
            self.reading_history[sensor_id] = []
        self.reading_history[sensor_id].append(value)
        if len(self.reading_history[sensor_id]) > 20:
            self.reading_history[sensor_id].pop(0)
        
        return True, None

    def validate_tank_level(self, value_cm: float, sensor_id: str) -> Tuple[bool, Optional[str]]:
        """
        Validate tank level reading.
        
        Args:
            value_cm: Tank level in cm
            sensor_id: Sensor identifier
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if value_cm < TANK_EMPTY_LEVEL_CM - 5 or value_cm > TANK_FULL_LEVEL_CM + 5:
            return False, f"Tank level {value_cm} cm outside expected range [{TANK_EMPTY_LEVEL_CM - 5}, {TANK_FULL_LEVEL_CM + 5}] cm"
        
        return True, None

    def validate_range(self, value: float, min_value: float, max_value: float, 
                      sensor_id: str, value_name: str = "value") -> Tuple[bool, Optional[str]]:
        """
        Generic range validation.
        
        Args:
            value: Value to validate
            min_value: Minimum allowed value
            max_value: Maximum allowed value
            sensor_id: Sensor identifier
            value_name: Name of the value for error messages
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if value < min_value or value > max_value:
            return False, f"{value_name} {value} outside valid range [{min_value}, {max_value}]"
        
        return True, None

    def reset_history(self, sensor_id: Optional[str] = None):
        """
        Reset validation history.
        
        Args:
            sensor_id: Sensor ID to reset, or None to reset all
        """
        if sensor_id:
            if sensor_id in self.reading_history:
                del self.reading_history[sensor_id]
        else:
            self.reading_history.clear()

