"""Hydraulic valve controller for zone sequencing."""
from typing import Dict, List, Optional
from app.hardware.valve_interface import ValveInterface
import time


class HydraulicValveController:
    """Controller for managing zone valves with sequencing."""

    def __init__(self, valve_interface: ValveInterface):
        """
        Initialize valve controller.
        
        Args:
            valve_interface: Valve interface instance
        """
        self.valve_interface = valve_interface
        self.current_zone: Optional[int] = None
        self.zone_sequence: List[int] = []
        self.sequence_index = 0

    def open_zone(self, zone_id: int, close_others: bool = True) -> bool:
        """
        Open valve for a specific zone.
        
        Args:
            zone_id: Zone ID to open
            close_others: Whether to close all other valves first
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if close_others:
                self.valve_interface.close_all_valves()
                time.sleep(0.5)  # Small delay for valves to close
            
            self.valve_interface.open_valve(zone_id)
            self.current_zone = zone_id
            
            return True
        except Exception as e:
            return False

    def close_zone(self, zone_id: int) -> bool:
        """
        Close valve for a specific zone.
        
        Args:
            zone_id: Zone ID to close
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.valve_interface.close_valve(zone_id)
            if self.current_zone == zone_id:
                self.current_zone = None
            return True
        except Exception as e:
            return False

    def close_all_zones(self) -> bool:
        """
        Close all zone valves.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            self.valve_interface.close_all_valves()
            self.current_zone = None
            return True
        except Exception as e:
            return False

    def set_zone_sequence(self, zone_ids: List[int]):
        """
        Set sequence of zones for sequential operation.
        
        Args:
            zone_ids: List of zone IDs in sequence order
        """
        self.zone_sequence = zone_ids
        self.sequence_index = 0

    def get_next_zone(self) -> Optional[int]:
        """
        Get next zone in sequence.
        
        Returns:
            Next zone ID or None if sequence is complete
        """
        if not self.zone_sequence or self.sequence_index >= len(self.zone_sequence):
            return None
        
        zone_id = self.zone_sequence[self.sequence_index]
        self.sequence_index += 1
        return zone_id

    def reset_sequence(self):
        """Reset sequence to beginning."""
        self.sequence_index = 0

    def get_current_zone(self) -> Optional[int]:
        """Get currently open zone."""
        return self.current_zone

    def is_zone_open(self, zone_id: int) -> bool:
        """Check if a zone valve is open."""
        return self.valve_interface.is_valve_open(zone_id)

    def get_open_zones(self) -> List[int]:
        """Get list of currently open zones."""
        return self.valve_interface.get_open_valves()

