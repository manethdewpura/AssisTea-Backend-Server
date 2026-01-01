"""Hydraulic pressure calculation accounting for elevation and slope."""
from typing import Dict, Optional
from app.config.config import (
    WATER_DENSITY_KG_PER_M3, GRAVITY_M_PER_S2,
    PRESSURE_LOSS_PER_DEGREE_SLOPE_KPA
)


class PressureCalculator:
    """Calculate required pump pressure accounting for elevation head and slope losses."""

    def __init__(self, reference_altitude_m: float = 0.0):
        """
        Initialize pressure calculator.
        
        Args:
            reference_altitude_m: Reference altitude (pump/base altitude) in meters
        """
        self.reference_altitude_m = reference_altitude_m

    def calculate_required_pressure(self, zone_altitude_m: float, zone_slope_degrees: float,
                                    base_pressure_kpa: float) -> Dict[str, float]:
        """
        Calculate required pump pressure for a zone.
        
        Args:
            zone_altitude_m: Zone altitude in meters
            zone_slope_degrees: Zone slope angle in degrees
            base_pressure_kpa: Base pressure requirement for the zone in kPa
            
        Returns:
            Dictionary with calculated pressure values
        """
        # Calculate elevation head pressure
        altitude_difference_m = zone_altitude_m - self.reference_altitude_m
        elevation_head_pressure_kpa = self._calculate_elevation_head(altitude_difference_m)
        
        # Calculate slope-related pressure loss
        slope_pressure_loss_kpa = self._calculate_slope_loss(zone_slope_degrees)
        
        # Total required pressure
        total_pressure_kpa = base_pressure_kpa + elevation_head_pressure_kpa + slope_pressure_loss_kpa
        
        return {
            'base_pressure_kpa': base_pressure_kpa,
            'elevation_head_kpa': elevation_head_pressure_kpa,
            'slope_loss_kpa': slope_pressure_loss_kpa,
            'total_required_pressure_kpa': total_pressure_kpa,
            'altitude_difference_m': altitude_difference_m,
            'zone_slope_degrees': zone_slope_degrees
        }

    def _calculate_elevation_head(self, altitude_difference_m: float) -> float:
        """
        Calculate pressure required to overcome elevation head.
        
        Pressure = ρ * g * h
        where ρ = water density, g = gravity, h = height difference
        
        Args:
            altitude_difference_m: Altitude difference in meters
            
        Returns:
            Pressure in kPa
        """
        # Convert to kPa (1 Pa = 0.001 kPa)
        pressure_pa = WATER_DENSITY_KG_PER_M3 * GRAVITY_M_PER_S2 * altitude_difference_m
        pressure_kpa = pressure_pa / 1000.0
        
        return pressure_kpa

    def _calculate_slope_loss(self, slope_degrees: float) -> float:
        """
        Calculate pressure loss due to slope.
        
        Args:
            slope_degrees: Slope angle in degrees
            
        Returns:
            Pressure loss in kPa
        """
        # Simple linear model: pressure loss increases with slope
        # More sophisticated models could account for pipe length, diameter, etc.
        slope_loss = abs(slope_degrees) * PRESSURE_LOSS_PER_DEGREE_SLOPE_KPA
        
        return slope_loss

    def calculate_zone_pressure_range(self, required_pressure_kpa: float,
                                     tolerance_kpa: float = 10.0) -> Dict[str, float]:
        """
        Calculate acceptable pressure range for a zone.
        
        Args:
            required_pressure_kpa: Required pressure in kPa
            tolerance_kpa: Pressure tolerance in kPa
            
        Returns:
            Dictionary with min, max, and target pressure
        """
        return {
            'target_pressure_kpa': required_pressure_kpa,
            'min_pressure_kpa': max(0.0, required_pressure_kpa - tolerance_kpa),
            'max_pressure_kpa': required_pressure_kpa + tolerance_kpa
        }

    def update_reference_altitude(self, reference_altitude_m: float):
        """Update reference altitude."""
        self.reference_altitude_m = reference_altitude_m

