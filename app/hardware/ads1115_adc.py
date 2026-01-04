"""ADS1115 ADC interface for analog sensor readings via I2C."""
try:
    import board
    import busio
    import adafruit_ads1x15.ads1115 as ADS
    from adafruit_ads1x15.analog_in import AnalogIn
    ADS1115_AVAILABLE = True
except (ImportError, NotImplementedError):
    ADS1115_AVAILABLE = False
    board = None
    busio = None
    ADS = None
    AnalogIn = None

from typing import Optional


class ADS1115ADC:
    """ADS1115 16-bit ADC interface for reading analog sensors via I2C."""

    # ADS1115 has 4 channels: 0, 1, 2, 3
    CHANNEL_0 = 0
    CHANNEL_1 = 1
    CHANNEL_2 = 2
    CHANNEL_3 = 3

    def __init__(self, i2c_address: int = 0x48, use_mock: bool = False):
        """
        Initialize ADS1115 ADC.
        
        Args:
            i2c_address: I2C address of ADS1115 (default: 0x48)
            use_mock: Use mock implementation for development
        """
        self.i2c_address = i2c_address
        self.use_mock = use_mock or not ADS1115_AVAILABLE
        self.ads = None
        self.channels = {}  # channel -> AnalogIn object
        
        if not self.use_mock:
            try:
                # Initialize I2C bus - use board.I2C() for automatic detection
                # This works better on Raspberry Pi than specifying pins directly
                i2c = board.I2C()  # Automatically uses the default I2C bus
                self.ads = ADS.ADS1115(i2c, address=i2c_address)
            except Exception as e:
                print(f"Warning: Could not initialize ADS1115, using mock: {str(e)}")
                self.use_mock = True
        
        # Mock values for development
        self.mock_values = {
            self.CHANNEL_0: 0.5,
            self.CHANNEL_1: 0.5,
            self.CHANNEL_2: 0.5,
            self.CHANNEL_3: 0.5,
        }

    def get_channel(self, channel: int) -> 'AnalogIn':
        """
        Get AnalogIn object for a channel.
        
        Args:
            channel: Channel number (0-3)
            
        Returns:
            AnalogIn object
        """
        if channel < 0 or channel > 3:
            raise ValueError(f"Channel must be between 0 and 3, got {channel}")
        
        if channel not in self.channels:
            if self.use_mock:
                # Return mock channel
                self.channels[channel] = MockAnalogIn(channel, self.mock_values[channel])
            else:
                # Create real AnalogIn channel - use integer directly
                self.channels[channel] = AnalogIn(self.ads, channel)
        
        return self.channels[channel]

    def read_voltage(self, channel: int) -> float:
        """
        Read voltage from a channel.
        
        Args:
            channel: Channel number (0-3)
            
        Returns:
            Voltage in volts
        """
        analog_in = self.get_channel(channel)
        return analog_in.voltage

    def read_normalized(self, channel: int) -> float:
        """
        Read normalized value (0.0 to 1.0) from a channel.
        
        Args:
            channel: Channel number (0-3)
            
        Returns:
            Normalized value between 0.0 and 1.0
        """
        analog_in = self.get_channel(channel)
        
        if self.use_mock:
            return self.mock_values[channel]
        
        # ADS1115 has ±4.096V range, normalize to 0-1
        # Assuming sensor outputs 0-3.3V (typical for Raspberry Pi)
        voltage = analog_in.voltage
        normalized = voltage / 3.3  # Normalize to 0-1 range
        return max(0.0, min(1.0, normalized))

    def set_mock_value(self, channel: int, value: float):
        """
        Set mock value for a channel (for testing).
        
        Args:
            channel: Channel number (0-3)
            value: Mock value (0.0 to 1.0)
        """
        if 0 <= channel <= 3:
            self.mock_values[channel] = max(0.0, min(1.0, value))
            # Update mock channel if it exists
            if channel in self.channels and isinstance(self.channels[channel], MockAnalogIn):
                self.channels[channel].set_value(value)


class MockAnalogIn:
    """Mock AnalogIn class for development/testing."""

    def __init__(self, channel: int, initial_value: float = 0.5):
        """
        Initialize mock analog input.
        
        Args:
            channel: Channel number
            initial_value: Initial normalized value (0.0 to 1.0)
        """
        self.channel = channel
        self._value = initial_value

    @property
    def voltage(self) -> float:
        """Get voltage (0-3.3V)."""
        return self._value * 3.3

    @property
    def value(self) -> int:
        """Get raw ADC value."""
        return int(self._value * 32767)  # 16-bit ADC max value

    def set_value(self, normalized_value: float):
        """Set normalized value (0.0 to 1.0)."""
        self._value = max(0.0, min(1.0, normalized_value))

