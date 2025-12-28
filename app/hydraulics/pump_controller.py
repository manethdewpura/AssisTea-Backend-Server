"""Pump controller for maintaining target pressure."""
from typing import Dict, Optional
import time
from app.hardware.pump_interface import PumpInterface
from app.config.config import PUMP_PRESSURE_TOLERANCE_KPA, PUMP_ADJUSTMENT_INTERVAL_SEC


class HydraulicPumpController:
    """Controller for maintaining pump pressure within target range."""

    def __init__(self, pump_interface: PumpInterface):
        """
        Initialize pump controller.
        
        Args:
            pump_interface: Pump interface instance
        """
        self.pump_interface = pump_interface
        self.target_pressure_kpa = 0.0
        self.last_adjustment_time = 0.0
        self.is_controlling = False

    def start_pressure_control(self, target_pressure_kpa: float):
        """
        Start pressure control mode.
        
        Args:
            target_pressure_kpa: Target pressure in kPa
        """
        self.target_pressure_kpa = target_pressure_kpa
        self.is_controlling = True
        
        # Start pump if not running
        if not self.pump_interface.is_running():
            self.pump_interface.start()
        
        # Set initial pressure
        self.pump_interface.set_pressure(target_pressure_kpa)

    def stop_pressure_control(self):
        """Stop pressure control and turn off pump."""
        self.is_controlling = False
        self.pump_interface.stop()

    def maintain_pressure(self, current_pressure_kpa: Optional[float] = None) -> Dict[str, any]:
        """
        Maintain target pressure by adjusting pump.
        
        Args:
            current_pressure_kpa: Current pressure reading (if None, reads from sensor)
            
        Returns:
            Dictionary with control status
        """
        if not self.is_controlling:
            return {
                'status': 'not_controlling',
                'message': 'Pressure control not active'
            }
        
        # Check if enough time has passed since last adjustment
        current_time = time.time()
        if current_time - self.last_adjustment_time < PUMP_ADJUSTMENT_INTERVAL_SEC:
            return {
                'status': 'waiting',
                'message': 'Waiting for adjustment interval'
            }
        
        # Get current pressure
        if current_pressure_kpa is None:
            current_pressure_kpa = self.pump_interface.get_current_pressure()
        
        # Calculate pressure difference
        pressure_diff = self.target_pressure_kpa - current_pressure_kpa
        
        # Check if pressure is within tolerance
        if abs(pressure_diff) <= PUMP_PRESSURE_TOLERANCE_KPA:
            return {
                'status': 'stable',
                'current_pressure_kpa': current_pressure_kpa,
                'target_pressure_kpa': self.target_pressure_kpa,
                'pressure_diff_kpa': pressure_diff,
                'message': 'Pressure within tolerance'
            }
        
        # Adjust pump pressure
        new_target = self.target_pressure_kpa + (pressure_diff * 0.5)  # Proportional adjustment
        self.pump_interface.set_pressure(new_target)
        self.last_adjustment_time = current_time
        
        return {
            'status': 'adjusted',
            'current_pressure_kpa': current_pressure_kpa,
            'target_pressure_kpa': self.target_pressure_kpa,
            'new_target_kpa': new_target,
            'pressure_diff_kpa': pressure_diff,
            'message': f'Adjusted pump pressure to {new_target:.1f} kPa'
        }

    def is_pressure_stable(self, current_pressure_kpa: Optional[float] = None) -> bool:
        """
        Check if pressure is stable within tolerance.
        
        Args:
            current_pressure_kpa: Current pressure reading
            
        Returns:
            True if pressure is stable, False otherwise
        """
        if not self.is_controlling:
            return False
        
        if current_pressure_kpa is None:
            current_pressure_kpa = self.pump_interface.get_current_pressure()
        
        pressure_diff = abs(self.target_pressure_kpa - current_pressure_kpa)
        return pressure_diff <= PUMP_PRESSURE_TOLERANCE_KPA

    def get_status(self) -> Dict[str, any]:
        """
        Get pump controller status.
        
        Returns:
            Dictionary with status information
        """
        current_pressure = self.pump_interface.get_current_pressure()
        
        return {
            'is_controlling': self.is_controlling,
            'is_running': self.pump_interface.is_running(),
            'target_pressure_kpa': self.target_pressure_kpa,
            'current_pressure_kpa': current_pressure,
            'pressure_diff_kpa': self.target_pressure_kpa - current_pressure if self.is_controlling else 0.0,
            'is_stable': self.is_pressure_stable(current_pressure) if self.is_controlling else False
        }

