"""Base sensor abstract class."""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from datetime import datetime


class BaseSensor(ABC):
    """Abstract base class for all sensors."""

    def __init__(self, sensor_id: str, zone_id: Optional[int] = None):
        """
        Initialize sensor.
        
        Args:
            sensor_id: Unique identifier for the sensor
            zone_id: Zone ID if sensor is zone-specific, None for system-wide sensors
        """
        self.sensor_id = sensor_id
        self.zone_id = zone_id
        self.last_reading: Optional[Dict[str, Any]] = None
        self.last_reading_time: Optional[datetime] = None
        self.is_healthy = True
        self.failure_count = 0

    @abstractmethod
    def read_raw(self) -> Dict[str, Any]:
        """
        Read raw sensor value.
        
        Returns:
            Dictionary with 'value' and 'unit' keys
        """
        pass

    @abstractmethod
    def read_standardized(self) -> Dict[str, Any]:
        """
        Read and return standardized sensor value.
        
        Returns:
            Dictionary with 'value', 'unit', 'raw_value', 'raw_unit', 'timestamp'
        """
        pass

    def get_last_reading(self) -> Optional[Dict[str, Any]]:
        """Get the last successful reading."""
        return self.last_reading

    def is_sensor_healthy(self) -> bool:
        """Check if sensor is healthy."""
        return self.is_healthy

    def mark_failure(self):
        """Mark sensor as having a failure."""
        self.failure_count += 1
        if self.failure_count >= 3:  # Configurable threshold
            self.is_healthy = False

    def mark_success(self):
        """Mark sensor as having a successful reading."""
        self.failure_count = 0
        self.is_healthy = True

