"""Fertilizer tank level sensor using HY-SR05 ultrasonic module."""
from typing import Dict, Any, Optional
from datetime import datetime
import time
from app.sensors.base import BaseSensor
from app.hardware.gpio_interface import GPIOInterface
from app.utils.noise_filter import NoiseFilter
from app.utils.unit_converter import UnitConverter


class TankLevelSensor(BaseSensor):
    """HY-SR05 ultrasonic tank level sensor.
    Sensor measures distance to water surface: high cm = empty, low cm = full.
    Calibration: empty_distance_cm (e.g. 100) = empty tank, full_distance_cm (e.g. 10) = full tank.
    """

    def __init__(self, sensor_id: str, gpio: GPIOInterface, trigger_pin: int, echo_pin: int,
                 tank_height_cm: float = 50.0,
                 empty_distance_cm: float = 100.0,
                 full_distance_cm: float = 10.0):
        """
        Initialize tank level sensor.

        Args:
            sensor_id: Unique sensor identifier
            gpio: GPIO interface instance
            trigger_pin: GPIO pin for trigger signal
            echo_pin: GPIO pin for echo signal
            tank_height_cm: Height of tank in cm (kept for backward compatibility / mock scaling)
            empty_distance_cm: Sensor distance reading when tank is empty (e.g. 100 cm)
            full_distance_cm: Sensor distance reading when tank is full (e.g. 10 cm)
        """
        super().__init__(sensor_id, zone_id=None)  # Tank is system-wide
        self.gpio = gpio
        self.trigger_pin = trigger_pin
        self.echo_pin = echo_pin
        self.tank_height_cm = tank_height_cm
        self.empty_distance_cm = empty_distance_cm
        self.full_distance_cm = full_distance_cm
        self._fill_range_cm = max(0.0, empty_distance_cm - full_distance_cm)
        self.noise_filter = NoiseFilter(window_size=3)
        self.unit_converter = UnitConverter()
        
        # Setup pins
        self.gpio.setup_pin(self.trigger_pin, 'output')
        self.gpio.setup_pin(self.echo_pin, 'input')
        
        # Initialize trigger pin to LOW
        self.gpio.write_pin(self.trigger_pin, False)

    def _read_distance_cm(self) -> float:
        """
        Read distance from ultrasonic sensor in cm.
        
        Returns:
            Distance in cm
        """
        # Only use analog path for MockGPIO (development). Real GPIO must use
        # pulse timing; RealGPIO.read_analog is digital 0/1 only, so a disconnected
        # echo pin would yield a fake "valid" reading and sensor would stay healthy.
        is_mock_gpio = type(self.gpio).__name__ == 'MockGPIO'
        if is_mock_gpio and hasattr(self.gpio, 'read_analog'):
            try:
                normalized = self.gpio.read_analog(self.echo_pin)
                # normalized 0 = full (low distance), 1 = empty (high distance)
                distance_cm = self.full_distance_cm + normalized * self._fill_range_cm
                return distance_cm
            except Exception:
                pass
        
        # Real hardware: use digital echo pulse timing (HY-SR05). Disconnected
        # sensor will timeout here and raise, so health is marked unhealthy.
        # Send trigger pulse (10 microseconds)
        self.gpio.write_pin(self.trigger_pin, True)
        time.sleep(0.00001)  # 10 microseconds
        self.gpio.write_pin(self.trigger_pin, False)
        
        # Wait for echo to go HIGH
        timeout = time.time() + 0.1  # 100ms timeout
        while not self.gpio.read_pin(self.echo_pin) and time.time() < timeout:
            pass
        
        if time.time() >= timeout:
            raise TimeoutError("Echo signal timeout")
        
        # Measure echo pulse duration
        start_time = time.time()
        timeout = start_time + 0.1
        while self.gpio.read_pin(self.echo_pin) and time.time() < timeout:
            pass
        
        if time.time() >= timeout:
            raise TimeoutError("Echo pulse timeout")
        
        end_time = time.time()
        pulse_duration = end_time - start_time
        
        # Calculate distance (speed of sound = 343 m/s = 0.0343 cm/μs)
        # Distance = (pulse_duration * speed_of_sound) / 2
        distance_cm = (pulse_duration * 34300) / 2
        
        return distance_cm

    def read_raw(self) -> Dict[str, Any]:
        """
        Read raw distance value from sensor.
        
        Returns:
            Dictionary with 'value' and 'unit'
        """
        try:
            distance_cm = self._read_distance_cm()
            
            self.mark_success()
            return {
                'value': distance_cm,
                'unit': 'cm'
            }
        except Exception as e:
            self.mark_failure()
            raise Exception(f"Failed to read tank level sensor {self.sensor_id}: {str(e)}")

    def read_standardized(self) -> Dict[str, Any]:
        """
        Read and return standardized tank level.
        API/sensor convention: received 0 = 100 cm (empty tank).
        """
        raw_data = self.read_raw()
        raw_distance_cm = raw_data['value']
        # Receiving 0 = 100 cm for the sensor (empty tank); some devices send 0 instead of 100
        if raw_distance_cm == 0:
            raw_distance_cm = self.empty_distance_cm

        # Apply noise filtering
        filtered_distance = self.noise_filter.filter(raw_distance_cm)

        # Invert: sensor distance high = empty, low = full.
        # Fill depth (cm) = empty_distance - distance, clamped to [0, fill_range]
        fill_depth_cm = self.empty_distance_cm - filtered_distance
        fill_depth_cm = max(0.0, min(self._fill_range_cm, fill_depth_cm))

        # Fill percentage (0% = empty, 100% = full)
        level_percent = (fill_depth_cm / self._fill_range_cm * 100.0) if self._fill_range_cm > 0 else 0.0
        level_percent = max(0.0, min(100.0, level_percent))

        # value = fill depth in cm (for fertigation / API); raw_value = sensor distance
        reading = {
            'value': fill_depth_cm,
            'unit': 'cm',
            'value_percent': level_percent,
            'raw_value': raw_distance_cm,
            'raw_unit': 'cm',
            'timestamp': datetime.now(),
            'sensor_id': self.sensor_id,
            'zone_id': self.zone_id
        }
        
        self.last_reading = reading
        self.last_reading_time = datetime.now()
        
        return reading

