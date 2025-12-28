"""Water pressure sensor interface."""
from typing import Dict, Any, Optional
from datetime import datetime
from app.sensors.base import BaseSensor
from app.hardware.ads1115_adc import ADS1115ADC
from app.utils.noise_filter import NoiseFilter
from app.utils.unit_converter import UnitConverter


class PressureSensor(BaseSensor):
    """Water pressure sensor with noise filtering via ADS1115 ADC."""

    def __init__(self, sensor_id: str, adc: ADS1115ADC, channel: int, zone_id: Optional[int] = None,
                 min_pressure_kpa: float = 0.0, max_pressure_kpa: float = 500.0):
        """
        Initialize pressure sensor.
        
        Args:
            sensor_id: Unique sensor identifier
            adc: ADS1115 ADC instance
            channel: ADC channel number (0-3)
            zone_id: Zone ID if zone-specific
            min_pressure_kpa: Minimum pressure in kPa (for calibration)
            max_pressure_kpa: Maximum pressure in kPa (for calibration)
        """
        super().__init__(sensor_id, zone_id)
        self.adc = adc
        self.channel = channel
        self.min_pressure_kpa = min_pressure_kpa
        self.max_pressure_kpa = max_pressure_kpa
        self.noise_filter = NoiseFilter(window_size=5)
        self.unit_converter = UnitConverter()

    def read_raw(self) -> Dict[str, Any]:
        """
        Read raw pressure value from sensor via ADS1115.
        
        Returns:
            Dictionary with 'value' and 'unit'
        """
        try:
            # Read normalized value (0.0 to 1.0) from ADC channel
            normalized_value = self.adc.read_normalized(self.channel)
            
            # Convert to pressure using calibration range
            pressure_range = self.max_pressure_kpa - self.min_pressure_kpa
            raw_pressure_kpa = self.min_pressure_kpa + (normalized_value * pressure_range)
            
            self.mark_success()
            return {
                'value': raw_pressure_kpa,
                'unit': 'kPa'
            }
        except Exception as e:
            self.mark_failure()
            raise Exception(f"Failed to read pressure sensor {self.sensor_id}: {str(e)}")

    def read_standardized(self) -> Dict[str, Any]:
        """
        Read and return standardized pressure value with noise filtering.
        
        Returns:
            Dictionary with standardized reading data
        """
        raw_data = self.read_raw()
        raw_value = raw_data['value']
        raw_unit = raw_data['unit']
        
        # Apply noise filtering
        filtered_value = self.noise_filter.filter(raw_value)
        
        # Ensure unit is standardized (kPa)
        standardized_value = self.unit_converter.convert_pressure(filtered_value, raw_unit, 'kPa')
        
        reading = {
            'value': standardized_value,
            'unit': 'kPa',
            'raw_value': raw_value,
            'raw_unit': raw_unit,
            'timestamp': datetime.now(),
            'sensor_id': self.sensor_id,
            'zone_id': self.zone_id
        }
        
        self.last_reading = reading
        self.last_reading_time = datetime.now()
        
        return reading

