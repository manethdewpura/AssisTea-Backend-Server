"""Capacitive soil moisture sensor (V2) interface."""
from typing import Dict, Any, Optional
from datetime import datetime
from app.sensors.base import BaseSensor
from app.hardware.ads1115_adc import ADS1115ADC
from app.utils.noise_filter import NoiseFilter
from app.utils.unit_converter import UnitConverter
from app.config.config import MIN_SOIL_MOISTURE_PERCENT, MAX_SOIL_MOISTURE_PERCENT


class SoilMoistureSensor(BaseSensor):
    """Capacitive soil moisture sensor V2 with calibration via ADS1115 ADC."""

    def __init__(self, sensor_id: str, adc: ADS1115ADC, channel: int, zone_id: Optional[int] = None,
                 dry_value: float = 0.0, wet_value: float = 1.0):
        """
        Initialize soil moisture sensor.
        
        Args:
            sensor_id: Unique sensor identifier
            adc: ADS1115 ADC instance
            channel: ADC channel number (0-3)
            zone_id: Zone ID
            dry_value: Sensor reading when soil is completely dry (0%) - normalized value
            wet_value: Sensor reading when soil is completely saturated (100%) - normalized value
        """
        super().__init__(sensor_id, zone_id)
        self.adc = adc
        self.channel = channel
        self.dry_value = dry_value
        self.wet_value = wet_value
        self.noise_filter = NoiseFilter(window_size=5)
        self.unit_converter = UnitConverter()

    def read_raw(self) -> Dict[str, Any]:
        """
        Read raw soil moisture value from sensor via ADS1115.
        
        Returns:
            Dictionary with 'value' and 'unit'
        """
        try:
            # Read normalized value (0.0 to 1.0) from ADC channel
            analog_value = self.adc.read_normalized(self.channel)
            
            self.mark_success()
            return {
                'value': analog_value,
                'unit': 'raw'  # Raw analog reading (normalized)
            }
        except Exception as e:
            self.mark_failure()
            raise Exception(f"Failed to read soil moisture sensor {self.sensor_id}: {str(e)}")

    def read_standardized(self) -> Dict[str, Any]:
        """
        Read and return standardized soil moisture percentage.
        
        Returns:
            Dictionary with standardized reading data
        """
        raw_data = self.read_raw()
        raw_value = raw_data['value']
        
        # Convert normalized value to voltage for validation
        voltage = raw_value * 3.3  # Convert normalized (0-1) to voltage (0-3.3V)
        
        # Check if voltage is below 1V (normalized < 0.303) - indicates unconnected sensor
        # 100% moisture is around 1.14V (0.344 normalized), so values below 1V are invalid
        if voltage < 1.0:  # 1V threshold
            self.mark_failure()
            raise Exception(
                f"Soil moisture sensor {self.sensor_id} appears unconnected or faulty "
                f"(voltage: {voltage:.3f}V < 1.0V, normalized: {raw_value:.4f})"
            )
        
        # Apply noise filtering
        filtered_value = self.noise_filter.filter(raw_value)
        
        # Check if filtered value is below wet_value (calibrated 100% point)
        # This indicates the sensor is reading below the calibrated wet point, which shouldn't happen
        # for a properly connected sensor (unless it's in a medium wetter than water)
        if filtered_value < self.wet_value:
            self.mark_failure()
            raise Exception(
                f"Soil moisture sensor {self.sensor_id} reading below calibrated wet value "
                f"(raw: {filtered_value:.4f} < wet_value: {self.wet_value:.4f}, voltage: {filtered_value*3.3:.3f}V). "
                f"Sensor may be unconnected or faulty."
            )
        
        # Convert to percentage using calibration
        # Map from [dry_value, wet_value] to [0%, 100%]
        if self.wet_value == self.dry_value:
            moisture_percent = 0.0
        else:
            # Normalize to 0-1 range
            normalized = (filtered_value - self.dry_value) / (self.wet_value - self.dry_value)
            # Clamp to 0-1 and convert to percentage
            moisture_percent = max(0.0, min(100.0, normalized * 100.0))
        
        # Validate the final moisture percentage is within expected range
        if moisture_percent < MIN_SOIL_MOISTURE_PERCENT or moisture_percent > MAX_SOIL_MOISTURE_PERCENT:
            self.mark_failure()
            raise Exception(
                f"Soil moisture {moisture_percent:.1f}% outside valid range "
                f"[{MIN_SOIL_MOISTURE_PERCENT}, {MAX_SOIL_MOISTURE_PERCENT}]%"
            )
        
        # Mark as successful if we got here
        self.mark_success()
        
        reading = {
            'value': moisture_percent,
            'unit': '%',
            'raw_value': raw_value,
            'raw_unit': 'raw',
            'timestamp': datetime.now(),
            'sensor_id': self.sensor_id,
            'zone_id': self.zone_id
        }
        
        self.last_reading = reading
        self.last_reading_time = datetime.now()
        
        return reading

