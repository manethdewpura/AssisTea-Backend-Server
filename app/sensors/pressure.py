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
                 min_pressure_kpa: float = 0.0, max_pressure_kpa: float = 600.0):
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
        # Detect disconnected sensor: floating ADC input often reads mid-scale (~0.5 normalized)
        self._floating_count = 0
        self._FLOATING_BAND_LOW = 0.48
        self._FLOATING_BAND_HIGH = 0.52
        self._FLOATING_THRESHOLD = 3  # consecutive reads in band -> treat as disconnected
        # Per-sensor zero baseline for real hardware so "no pressure" reads ~0 kPa,
        # mirroring the behavior in the standalone ADS1115 diagnostic script.
        self._zero_kpa: Optional[float] = None

    def _adc_voltage_to_sensor_voltage(self, v_adc: float) -> float:
        """
        Convert ADS1115 voltage (0–3.3V) back to sensor output (0–5V)
        assuming a linear 5V→3.3V level shifter (same convention as test2.py).
        """
        scale = 5.0 / 3.3
        return v_adc * scale

    def _sensor_voltage_to_pressure_kpa(self, v_sensor: float) -> float:
        """
        Convert sensor output voltage (0.5–4.5V) to pressure in kPa.
        0.5V -> 0 kPa
        4.5V -> 500 kPa
        """
        # Clamp to the physical sensor range
        v_sensor = max(0.0, min(5.0, v_sensor))
        if v_sensor <= 0.5:
            return 0.0

        span_v = 4.5 - 0.5  # 4.0V span
        ratio = (v_sensor - 0.5) / span_v
        # Sensor is rated for 0–500 kPa; keep that range here
        return max(0.0, min(500.0, ratio * 500.0))

    def read_raw(self) -> Dict[str, Any]:
        """
        Read raw pressure value from sensor via ADS1115.
        
        Returns:
            Dictionary with 'value' and 'unit'
        """
        try:
            # Mock mode: preserve existing linear mapping using normalized value and
            # configured min/max range so tests and mock APIs behave as before.
            if getattr(self.adc, 'use_mock', True):
                normalized_value = self.adc.read_normalized(self.channel)
                pressure_range = self.max_pressure_kpa - self.min_pressure_kpa
                raw_pressure_kpa = self.min_pressure_kpa + (normalized_value * pressure_range)
                # No floating detection / baseline in mock mode
            else:
                # Real hardware: read actual ADC voltage (0–3.3V)
                v_adc = self.adc.read_voltage(self.channel)

                # For floating/disconnected detection, work with normalized 0–1 value
                normalized_value = max(0.0, min(1.0, v_adc / 3.3)) if v_adc >= 0.0 else 0.0

                # Only check for floating (disconnected) input when using real hardware
                if self._FLOATING_BAND_LOW <= normalized_value <= self._FLOATING_BAND_HIGH:
                    self._floating_count += 1
                    if self._floating_count >= self._FLOATING_THRESHOLD:
                        self.mark_failure()
                        raise Exception(
                            f"Pressure sensor {self.sensor_id} appears disconnected "
                            f"(floating input reads ~{normalized_value:.3f} for {self._floating_count} reads)"
                        )
                else:
                    self._floating_count = 0

                # Convert ADC voltage -> sensor voltage (0–5V) -> pressure (0–500 kPa),
                # using the same calibration logic as the standalone test script.
                v_sensor = self._adc_voltage_to_sensor_voltage(v_adc)
                raw_pressure_kpa = self._sensor_voltage_to_pressure_kpa(v_sensor)

                # Capture per-sensor baseline on first successful read and treat it as 0 kPa,
                # so an idle sensor resting near ~50 kPa will report ~0 kPa.
                if self._zero_kpa is None:
                    self._zero_kpa = raw_pressure_kpa

                raw_pressure_kpa = max(0.0, raw_pressure_kpa - self._zero_kpa)

            self._floating_count = 0  # Reset on successful valid (non-floating) read
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

