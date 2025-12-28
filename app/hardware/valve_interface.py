"""Solenoid valve control interface."""
from abc import ABC, abstractmethod
from typing import Dict
from app.hardware.gpio_interface import GPIOInterface


class ValveInterface(ABC):
    """Abstract interface for valve control."""

    @abstractmethod
    def open_valve(self, zone_id: int):
        """Open valve for a specific zone."""
        pass

    @abstractmethod
    def close_valve(self, zone_id: int):
        """Close valve for a specific zone."""
        pass

    @abstractmethod
    def close_all_valves(self):
        """Close all valves."""
        pass

    @abstractmethod
    def is_valve_open(self, zone_id: int) -> bool:
        """Check if valve for a zone is open."""
        pass

    @abstractmethod
    def get_open_valves(self) -> list:
        """Get list of currently open zone IDs."""
        pass


class SolenoidValveController(ValveInterface):
    """Solenoid valve controller using GPIO."""

    def __init__(self, gpio: GPIOInterface, zone_pins: Dict[int, int]):
        """
        Initialize valve controller.
        
        Args:
            gpio: GPIO interface instance
            zone_pins: Dictionary mapping zone_id to GPIO pin number
        """
        self.gpio = gpio
        self.zone_pins = zone_pins
        self.valve_states: Dict[int, bool] = {}  # zone_id -> is_open
        
        # Setup all valve pins as outputs and close them
        for zone_id, pin in self.zone_pins.items():
            self.gpio.setup_pin(pin, 'output')
            self.gpio.write_pin(pin, False)  # False = closed (assuming active-low or normally closed)
            self.valve_states[zone_id] = False

    def open_valve(self, zone_id: int):
        """Open valve for a specific zone."""
        if zone_id not in self.zone_pins:
            raise ValueError(f"Zone {zone_id} not configured")
        
        pin = self.zone_pins[zone_id]
        self.gpio.write_pin(pin, True)  # True = open
        self.valve_states[zone_id] = True

    def close_valve(self, zone_id: int):
        """Close valve for a specific zone."""
        if zone_id not in self.zone_pins:
            raise ValueError(f"Zone {zone_id} not configured")
        
        pin = self.zone_pins[zone_id]
        self.gpio.write_pin(pin, False)  # False = closed
        self.valve_states[zone_id] = False

    def close_all_valves(self):
        """Close all valves."""
        for zone_id in list(self.valve_states.keys()):
            self.close_valve(zone_id)

    def is_valve_open(self, zone_id: int) -> bool:
        """Check if valve for a zone is open."""
        return self.valve_states.get(zone_id, False)

    def get_open_valves(self) -> list:
        """Get list of currently open zone IDs."""
        return [zone_id for zone_id, is_open in self.valve_states.items() if is_open]

