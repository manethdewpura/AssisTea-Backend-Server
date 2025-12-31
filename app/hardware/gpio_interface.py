"""Abstract GPIO interface for hardware abstraction."""
from abc import ABC, abstractmethod


class GPIOInterface(ABC):
    """Abstract base class for GPIO operations."""

    @abstractmethod
    def setup_pin(self, pin: int, mode: str, pull_up_down: str = None):
        """
        Setup a GPIO pin.
        
        Args:
            pin: GPIO pin number
            mode: 'input' or 'output'
            pull_up_down: 'up', 'down', or None
        """
        pass

    @abstractmethod
    def read_pin(self, pin: int) -> bool:
        """
        Read digital value from GPIO pin.
        
        Args:
            pin: GPIO pin number
            
        Returns:
            True for HIGH, False for LOW
        """
        pass

    @abstractmethod
    def write_pin(self, pin: int, value: bool):
        """
        Write digital value to GPIO pin.
        
        Args:
            pin: GPIO pin number
            value: True for HIGH, False for LOW
        """
        pass

    @abstractmethod
    def read_analog(self, pin: int) -> float:
        """
        Read analog value from GPIO pin (0.0 to 1.0).
        
        Args:
            pin: GPIO pin number
            
        Returns:
            Analog value between 0.0 and 1.0
        """
        pass

    @abstractmethod
    def cleanup(self):
        """Cleanup GPIO resources."""
        pass

    @abstractmethod
    def cleanup_pin(self, pin: int):
        """Cleanup a specific GPIO pin."""
        pass

