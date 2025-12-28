"""Fertilizer tank level sensor using HY-SR05 ultrasonic module."""
from typing import Dict, Any, Optional
from datetime import datetime
import time
from app.sensors.base import BaseSensor
from app.hardware.gpio_interface import GPIOInterface
from app.utils.noise_filter import NoiseFilter
from app.utils.unit_converter import UnitConverter


class TankLevelSensor(BaseSensor):
    """HY-SR05 ultrasonic tank level sensor."""

    def __init__(self, sensor_id: str, gpio: GPIOInterface, trigger_pin: int, echo_pin: int,
                 tank_height_cm: float = 50.0):
        """
        Initialize tank level sensor.
        
        Args:
            sensor_id: Unique sensor identifier
            gpio: GPIO interface instance
            trigger_pin: GPIO pin for trigger signal
            echo_pin: GPIO pin for echo signal
            tank_height_cm: Height of tank in cm
        """
        super().__init__(sensor_id, zone_id=None)  # Tank is system-wide
        self.gpio = gpio
        self.trigger_pin = trigger_pin
        self.echo_pin = echo_pin
        self.tank_height_cm = tank_height_cm
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
        
        Returns:
            Dictionary with standardized reading data (level in cm and %)
        """
        raw_data = self.read_raw()
        raw_distance_cm = raw_data['value']
        
        # Apply noise filtering
        filtered_distance = self.noise_filter.filter(raw_distance_cm)
        
        # Calculate level (distance from sensor to liquid surface)
        # Level = tank_height - distance
        level_cm = max(0.0, self.tank_height_cm - filtered_distance)
        
        # Calculate percentage
        level_percent = (level_cm / self.tank_height_cm) * 100.0 if self.tank_height_cm > 0 else 0.0
        level_percent = max(0.0, min(100.0, level_percent))
        
        reading = {
            'value': level_cm,
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

