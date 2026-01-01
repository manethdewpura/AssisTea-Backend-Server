"""Slope and altitude sensor interface."""
from typing import Dict, Any, Optional
from datetime import datetime
from app.sensors.base import BaseSensor
from app.utils.noise_filter import NoiseFilter
from app.utils.unit_converter import UnitConverter


class SlopeAltitudeSensor(BaseSensor):
    """Sensor for slope and altitude readings."""

    def __init__(self, sensor_id: str, zone_id: Optional[int] = None,
                 altitude_m: float = 0.0, slope_degrees: float = 0.0):
        """
        Initialize slope/altitude sensor.
        
        Args:
            sensor_id: Unique sensor identifier
            zone_id: Zone ID
            altitude_m: Altitude in meters (can be static or from GPS/barometer)
            slope_degrees: Slope angle in degrees (can be static or from accelerometer)
        """
        super().__init__(sensor_id, zone_id)
        self.altitude_m = altitude_m
        self.slope_degrees = slope_degrees
        self.noise_filter = NoiseFilter(window_size=3)
        self.unit_converter = UnitConverter()
        
        # Note: In a real implementation, this would interface with GPS/IMU hardware
        # For now, we use static values that can be configured per zone

    def read_raw(self) -> Dict[str, Any]:
        """
        Read raw altitude and slope values.
        
        Returns:
            Dictionary with altitude and slope values
        """
        try:
            # In real implementation, this would read from GPS/IMU
            # For now, return configured values
            self.mark_success()
            return {
                'altitude': self.altitude_m,
                'altitude_unit': 'm',
                'slope': self.slope_degrees,
                'slope_unit': 'degrees'
            }
        except Exception as e:
            self.mark_failure()
            raise Exception(f"Failed to read slope/altitude sensor {self.sensor_id}: {str(e)}")

    def read_standardized(self) -> Dict[str, Any]:
        """
        Read and return standardized altitude and slope values.
        
        Returns:
            Dictionary with standardized reading data
        """
        raw_data = self.read_raw()
        
        # Apply noise filtering (if values change over time)
        altitude_m = self.noise_filter.filter(raw_data['altitude'])
        slope_degrees = self.noise_filter.filter(raw_data['slope'])
        
        reading = {
            'altitude': altitude_m,
            'altitude_unit': 'm',
            'slope': slope_degrees,
            'slope_unit': 'degrees',
            'timestamp': datetime.now(),
            'sensor_id': self.sensor_id,
            'zone_id': self.zone_id
        }
        
        self.last_reading = reading
        self.last_reading_time = datetime.now()
        
        return reading

    def set_altitude(self, altitude_m: float):
        """Update altitude value (for static configuration)."""
        self.altitude_m = altitude_m

    def set_slope(self, slope_degrees: float):
        """Update slope value (for static configuration)."""
        self.slope_degrees = slope_degrees

