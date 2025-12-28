"""Pump control interface."""
from abc import ABC, abstractmethod
from app.hardware.gpio_interface import GPIOInterface


class PumpInterface(ABC):
    """Abstract interface for pump control."""

    @abstractmethod
    def start(self):
        """Start the pump."""
        pass

    @abstractmethod
    def stop(self):
        """Stop the pump."""
        pass

    @abstractmethod
    def is_running(self) -> bool:
        """Check if pump is running."""
        pass

    @abstractmethod
    def set_pressure(self, target_pressure_kpa: float):
        """
        Set target pressure for the pump.
        
        Args:
            target_pressure_kpa: Target pressure in kPa
        """
        pass

    @abstractmethod
    def get_current_pressure(self) -> float:
        """
        Get current pump pressure.
        
        Returns:
            Current pressure in kPa
        """
        pass


class SimplePumpController(PumpInterface):
    """Simple pump controller using GPIO."""

    def __init__(self, gpio: GPIOInterface, pump_pin: int, pressure_sensor_pin: int = None):
        """
        Initialize pump controller.
        
        Args:
            gpio: GPIO interface instance
            pump_pin: GPIO pin for pump control
            pressure_sensor_pin: GPIO pin for pressure sensor (optional)
        """
        self.gpio = gpio
        self.pump_pin = pump_pin
        self.pressure_sensor_pin = pressure_sensor_pin
        self.is_pump_running = False
        self.target_pressure = 0.0
        
        # Setup pump pin as output
        self.gpio.setup_pin(self.pump_pin, 'output')
        self.gpio.write_pin(self.pump_pin, False)
        
        # Setup pressure sensor if provided
        if self.pressure_sensor_pin:
            self.gpio.setup_pin(self.pressure_sensor_pin, 'input')

    def start(self):
        """Start the pump."""
        self.gpio.write_pin(self.pump_pin, True)
        self.is_pump_running = True

    def stop(self):
        """Stop the pump."""
        self.gpio.write_pin(self.pump_pin, False)
        self.is_pump_running = False

    def is_running(self) -> bool:
        """Check if pump is running."""
        return self.is_pump_running

    def set_pressure(self, target_pressure_kpa: float):
        """Set target pressure (for variable speed pumps, this would adjust speed)."""
        self.target_pressure = target_pressure_kpa
        # For simple on/off pumps, we just ensure pump is running
        # Actual pressure control would be handled by monitoring and adjusting
        if not self.is_pump_running and target_pressure_kpa > 0:
            self.start()

    def get_current_pressure(self) -> float:
        """
        Get current pump pressure.
        Note: This is a placeholder. In real implementation, use PressureSensor
        which reads from ADS1115 ADC.
        """
        # If no sensor pin configured, return target pressure when running, 0 when stopped
        # Actual pressure reading should be done via PressureSensor using ADS1115
        return self.target_pressure if self.is_pump_running else 0.0

