"""Real GPIO implementation for Raspberry Pi."""
try:
    import RPi.GPIO as GPIO
    RPI_GPIO_AVAILABLE = True
except ImportError:
    RPI_GPIO_AVAILABLE = False
    GPIO = None

from app.hardware.gpio_interface import GPIOInterface


class RealGPIO(GPIOInterface):
    """Real GPIO implementation using RPi.GPIO."""

    def __init__(self):
        """Initialize real GPIO."""
        if not RPI_GPIO_AVAILABLE:
            raise ImportError("RPi.GPIO is not available. Install it with: pip install RPi.GPIO")
        
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        self.setup_pins = set()

    def setup_pin(self, pin: int, mode: str, pull_up_down: str = None):
        """Setup a GPIO pin."""
        if mode == 'input':
            pull = None
            if pull_up_down == 'up':
                pull = GPIO.PUD_UP
            elif pull_up_down == 'down':
                pull = GPIO.PUD_DOWN
            
            GPIO.setup(pin, GPIO.IN, pull_up_down=pull)
        elif mode == 'output':
            GPIO.setup(pin, GPIO.OUT)
        else:
            raise ValueError(f"Invalid mode: {mode}")
        
        self.setup_pins.add(pin)

    def read_pin(self, pin: int) -> bool:
        """Read digital value from GPIO pin."""
        if pin not in self.setup_pins:
            raise ValueError(f"Pin {pin} not set up")
        
        return GPIO.input(pin) == GPIO.HIGH

    def write_pin(self, pin: int, value: bool):
        """Write digital value to GPIO pin."""
        if pin not in self.setup_pins:
            raise ValueError(f"Pin {pin} not set up")
        
        GPIO.output(pin, GPIO.HIGH if value else GPIO.LOW)

    def read_analog(self, pin: int) -> float:
        """
        Read analog value from GPIO pin.
        Note: Raspberry Pi doesn't have native analog inputs.
        This assumes an ADC (like MCP3008) is being used via SPI.
        For now, returns a normalized value based on digital reading.
        """
        # This is a placeholder - actual implementation would use an ADC
        # For now, return digital reading as 0.0 or 1.0
        digital = self.read_pin(pin)
        return 1.0 if digital else 0.0

    def cleanup(self):
        """Cleanup GPIO resources."""
        GPIO.cleanup()
        self.setup_pins.clear()

    def cleanup_pin(self, pin: int):
        """Cleanup a specific GPIO pin."""
        if pin in self.setup_pins:
            GPIO.cleanup(pin)
            self.setup_pins.remove(pin)

