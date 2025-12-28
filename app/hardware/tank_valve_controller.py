"""Tank valve controller for inlet/outlet solenoids."""
from app.hardware.gpio_interface import GPIOInterface


class TankValveController:
    """Simple controller for tank inlet/outlet valves."""

    def __init__(self, gpio: GPIOInterface, inlet_pin: int, outlet_pin: int):
        """
        Initialize tank valve controller.
        
        Args:
            gpio: GPIO interface instance
            inlet_pin: GPIO pin for inlet solenoid
            outlet_pin: GPIO pin for outlet solenoid
        """
        self.gpio = gpio
        self.inlet_pin = inlet_pin
        self.outlet_pin = outlet_pin
        
        # Setup pins as outputs
        self.gpio.setup_pin(self.inlet_pin, 'output')
        self.gpio.setup_pin(self.outlet_pin, 'output')
        
        # Initialize to closed
        self.gpio.write_pin(self.inlet_pin, False)
        self.gpio.write_pin(self.outlet_pin, False)

    def open_inlet(self):
        """Open inlet valve."""
        self.gpio.write_pin(self.inlet_pin, True)

    def close_inlet(self):
        """Close inlet valve."""
        self.gpio.write_pin(self.inlet_pin, False)

    def open_outlet(self):
        """Open outlet valve."""
        self.gpio.write_pin(self.outlet_pin, True)

    def close_outlet(self):
        """Close outlet valve."""
        self.gpio.write_pin(self.outlet_pin, False)

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

