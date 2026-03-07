"""Fertilizer pump solenoid valve controller."""
from app.hardware.gpio_interface import GPIOInterface
from app.services.solenoid_state_manager import SolenoidStateManager
from typing import Optional


class FertilizerPumpSolenoid:
    """Controller for fertilizer pump solenoid valve (opens with tank outlet for fertigation flush)."""

    def __init__(self, gpio: GPIOInterface, solenoid_pin: int, state_manager: Optional[SolenoidStateManager] = None):
        """
        Initialize fertilizer pump solenoid controller.

        Args:
            gpio: GPIO interface instance
            solenoid_pin: GPIO pin for fertilizer pump solenoid valve
            state_manager: Optional solenoid state manager for persistent storage
        """
        self.gpio = gpio
        self.solenoid_pin = solenoid_pin
        self.state_manager = state_manager
        self.solenoid_name = 'fertilizer_pump_solenoid'

        # Setup pin as output
        self.gpio.setup_pin(self.solenoid_pin, 'output')

        # Load last known state from database if available
        if self.state_manager:
            saved_state = self.state_manager.get_solenoid_state(self.solenoid_name)
            if saved_state is not None:
                self.gpio.write_pin(self.solenoid_pin, saved_state)
            else:
                self.gpio.write_pin(self.solenoid_pin, False)
                self.state_manager.set_solenoid_state(self.solenoid_name, False)
        else:
            self.gpio.write_pin(self.solenoid_pin, False)

    def open(self):
        """Open fertilizer pump solenoid valve."""
        self.gpio.write_pin(self.solenoid_pin, True)
        if self.state_manager:
            self.state_manager.set_solenoid_state(self.solenoid_name, True)

    def close(self):
        """Close fertilizer pump solenoid valve."""
        self.gpio.write_pin(self.solenoid_pin, False)
        if self.state_manager:
            self.state_manager.set_solenoid_state(self.solenoid_name, False)

    def is_open(self) -> bool:
        """Check if fertilizer pump solenoid valve is open."""
        return self.gpio.read_pin(self.solenoid_pin)
