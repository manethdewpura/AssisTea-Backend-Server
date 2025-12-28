"""Mock GPIO implementation for development/testing."""
import random
import time
from typing import Dict
from app.hardware.gpio_interface import GPIOInterface


class MockGPIO(GPIOInterface):
    """Mock GPIO implementation that simulates hardware behavior."""

    def __init__(self):
        """Initialize mock GPIO."""
        self.pins: Dict[int, Dict] = {}  # pin -> {mode, value, pull_up_down}
        self.analog_values: Dict[int, float] = {}  # pin -> analog value
        self.pin_states: Dict[int, bool] = {}  # pin -> digital state

    def setup_pin(self, pin: int, mode: str, pull_up_down: str = None):
        """Setup a GPIO pin."""
        if pin not in self.pins:
            self.pins[pin] = {
                'mode': mode,
                'pull_up_down': pull_up_down,
                'value': False if mode == 'output' else (pull_up_down == 'up')
            }
            self.pin_states[pin] = self.pins[pin]['value']
            # Initialize analog value for input pins
            if mode == 'input':
                self.analog_values[pin] = random.uniform(0.0, 1.0)

    def read_pin(self, pin: int) -> bool:
        """Read digital value from GPIO pin."""
        if pin not in self.pins:
            raise ValueError(f"Pin {pin} not set up")
        
        if self.pins[pin]['mode'] == 'input':
            # Simulate some variation in readings
            if random.random() < 0.1:  # 10% chance of noise
                self.pin_states[pin] = not self.pin_states[pin]
        
        return self.pin_states.get(pin, False)

    def write_pin(self, pin: int, value: bool):
        """Write digital value to GPIO pin."""
        if pin not in self.pins:
            raise ValueError(f"Pin {pin} not set up")
        
        if self.pins[pin]['mode'] != 'output':
            raise ValueError(f"Pin {pin} is not configured as output")
        
        self.pin_states[pin] = value
        self.pins[pin]['value'] = value

    def read_analog(self, pin: int) -> float:
        """Read analog value from GPIO pin."""
        if pin not in self.pins:
            raise ValueError(f"Pin {pin} not set up")
        
        if pin not in self.analog_values:
            self.analog_values[pin] = random.uniform(0.0, 1.0)
        else:
            # Simulate small variations
            self.analog_values[pin] += random.uniform(-0.01, 0.01)
            self.analog_values[pin] = max(0.0, min(1.0, self.analog_values[pin]))
        
        return self.analog_values[pin]

    def set_analog_value(self, pin: int, value: float):
        """Manually set analog value for testing."""
        self.analog_values[pin] = max(0.0, min(1.0, value))

    def cleanup(self):
        """Cleanup GPIO resources."""
        self.pins.clear()
        self.pin_states.clear()
        self.analog_values.clear()

    def cleanup_pin(self, pin: int):
        """Cleanup a specific GPIO pin."""
        if pin in self.pins:
            del self.pins[pin]
        if pin in self.pin_states:
            del self.pin_states[pin]
        if pin in self.analog_values:
            del self.analog_values[pin]

