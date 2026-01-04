"""Tank valve controller for inlet/outlet solenoids."""
from app.hardware.gpio_interface import GPIOInterface
from app.services.solenoid_state_manager import SolenoidStateManager
from typing import Optional


class TankValveController:
    """Simple controller for tank inlet/outlet valves."""

    def __init__(self, gpio: GPIOInterface, inlet_pin: int, outlet_pin: int, 
                 state_manager: Optional[SolenoidStateManager] = None):
        """
        Initialize tank valve controller.
        
        Args:
            gpio: GPIO interface instance
            inlet_pin: GPIO pin for inlet solenoid
            outlet_pin: GPIO pin for outlet solenoid
            state_manager: Optional solenoid state manager for persistent storage
        """
        self.gpio = gpio
        self.inlet_pin = inlet_pin
        self.outlet_pin = outlet_pin
        self.state_manager = state_manager
        self.inlet_name = 'tank_inlet_solenoid'
        self.outlet_name = 'tank_outlet_solenoid'
        
        # Setup pins as outputs
        self.gpio.setup_pin(self.inlet_pin, 'output')
        self.gpio.setup_pin(self.outlet_pin, 'output')
        
        # Load last known states from database if available
        if self.state_manager:
            # Load inlet state
            inlet_state = self.state_manager.get_solenoid_state(self.inlet_name)
            if inlet_state is not None:
                self.gpio.write_pin(self.inlet_pin, inlet_state)
            else:
                self.gpio.write_pin(self.inlet_pin, False)
                self.state_manager.set_solenoid_state(self.inlet_name, False)
            
            # Load outlet state
            outlet_state = self.state_manager.get_solenoid_state(self.outlet_name)
            if outlet_state is not None:
                self.gpio.write_pin(self.outlet_pin, outlet_state)
            else:
                self.gpio.write_pin(self.outlet_pin, False)
                self.state_manager.set_solenoid_state(self.outlet_name, False)
        else:
            # Initialize to closed
            self.gpio.write_pin(self.inlet_pin, False)
            self.gpio.write_pin(self.outlet_pin, False)

    def open_inlet(self):
        """Open inlet valve."""
        self.gpio.write_pin(self.inlet_pin, True)
        if self.state_manager:
            self.state_manager.set_solenoid_state(self.inlet_name, True)

    def close_inlet(self):
        """Close inlet valve."""
        self.gpio.write_pin(self.inlet_pin, False)
        if self.state_manager:
            self.state_manager.set_solenoid_state(self.inlet_name, False)

    def open_outlet(self):
        """Open outlet valve."""
        self.gpio.write_pin(self.outlet_pin, True)
        if self.state_manager:
            self.state_manager.set_solenoid_state(self.outlet_name, True)

    def close_outlet(self):
        """Close outlet valve."""
        self.gpio.write_pin(self.outlet_pin, False)
        if self.state_manager:
            self.state_manager.set_solenoid_state(self.outlet_name, False)

    def close_all(self):
        """Close both valves."""
        self.close_inlet()
        self.close_outlet()

    def is_inlet_open(self) -> bool:
        """Check if inlet valve is open."""
        return self.gpio.read_pin(self.inlet_pin)

    def is_outlet_open(self) -> bool:
        """Check if outlet valve is open."""
        return self.gpio.read_pin(self.outlet_pin)

