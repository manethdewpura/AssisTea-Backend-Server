"""Slope sensor interface.

Altitude support has been removed; this sensor now only reports slope in
degrees for the single-zone system configuration.
"""
from typing import Dict, Any, Optional
from datetime import datetime
from app.sensors.base import BaseSensor
from app.utils.noise_filter import NoiseFilter
from app.utils.unit_converter import UnitConverter


class SlopeSensor(BaseSensor):
    """Sensor for slope readings in degrees."""

    def __init__(self, sensor_id: str, zone_id: Optional[int] = None,
                 slope_degrees: float = 0.0):
        """
        Initialize slope sensor.
        
        Args:
            sensor_id: Unique sensor identifier
            zone_id: Zone ID
            slope_degrees: Slope angle in degrees (can be static or from accelerometer)
        """
        super().__init__(sensor_id, zone_id)
        self.slope_degrees = slope_degrees
        self.noise_filter = NoiseFilter(window_size=3)
        self.unit_converter = UnitConverter()
        
        # Note: In a real implementation, this would interface with GPS/IMU hardware
        # For now, we use static values that can be configured per zone

    def read_raw(self) -> Dict[str, Any]:
        """
        Read raw slope value.
        
        Returns:
            Dictionary with slope value
        """
        try:
            # In real implementation, this would read from GPS/IMU
            # For now, return configured value
            self.mark_success()
            return {
                'slope': self.slope_degrees,
                'slope_unit': 'degrees'
            }
        except Exception as e:
            self.mark_failure()
            raise Exception(f"Failed to read slope sensor {self.sensor_id}: {str(e)}")

    def read_standardized(self) -> Dict[str, Any]:
        """
        Read and return standardized slope value.
        
        Returns:
            Dictionary with standardized reading data
        """
        raw_data = self.read_raw()
        
        # Apply noise filtering (if values change over time)
        slope_degrees = self.noise_filter.filter(raw_data['slope'])
        
        reading = {
            'slope': slope_degrees,
            'slope_unit': 'degrees',
            'timestamp': datetime.now(),
            'sensor_id': self.sensor_id,
            'zone_id': self.zone_id
        }
        
        self.last_reading = reading
        self.last_reading_time = datetime.now()
        
        return reading

    def set_slope(self, slope_degrees: float):
        """Update slope value (for static configuration)."""
        self.slope_degrees = slope_degrees

