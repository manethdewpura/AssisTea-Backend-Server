"""Hydraulic pressure calculation using Darcy–Weisbach and minor losses."""
import math
from typing import Dict
from app.config.config import (
    WATER_DENSITY_KG_PER_M3,
    GRAVITY_M_PER_S2,
    WATER_DYNAMIC_VISCOSITY_PA_S,
    PIPE_LENGTH_M,
    PIPE_DIAMETER_M,
    ESTIMATED_FLOW_RATE_M3_PER_S,
    DARCY_FRICTION_FACTOR,
    MINOR_LOSS_COEFFICIENT_K,
    PRESSURE_SAFETY_MARGIN_PERCENT,
)


class PressureCalculator:
    """
    Calculate required pump pressure using physically realistic hydraulics.
    
    Components:
    - Static head:      P_static   = ρ g h,  h = L · sin(θ)
    - Friction losses:  ΔP_fric    = f (L/D) (ρ v² / 2)
    - Minor losses:     ΔP_minor   = K (ρ v² / 2)
    - Safety margin:    P_total    = (base + P_static + ΔP_fric + ΔP_minor) · (1 + margin%)
    
    All pressures are returned in kPa; inputs are in SI units.
    """

    def __init__(
        self,
        reference_altitude_m: float = 0.0,
        pipe_length_m: float = PIPE_LENGTH_M,
        pipe_diameter_m: float = PIPE_DIAMETER_M,
        flow_rate_m3_per_s: float = ESTIMATED_FLOW_RATE_M3_PER_S,
        friction_factor: float = DARCY_FRICTION_FACTOR,
        minor_loss_coefficient_k: float = MINOR_LOSS_COEFFICIENT_K,
        safety_margin_percent: float = PRESSURE_SAFETY_MARGIN_PERCENT,
    ):
        """
        Initialize pressure calculator.

        Args:
            reference_altitude_m: Kept for backwards compatibility (absolute altitude);
                                  static head for irrigation is derived from pipe geometry.
            pipe_length_m: Total pipe length L in meters.
            pipe_diameter_m: Internal pipe diameter D in meters.
            flow_rate_m3_per_s: Estimated volumetric flow rate Q in m³/s.
            friction_factor: Darcy friction factor f (dimensionless). If <= 0, it
                             will be estimated from Reynolds number.
            minor_loss_coefficient_k: Aggregate minor loss coefficient K (dimensionless).
            safety_margin_percent: Safety margin percentage applied to the total pressure.
        """
        self.reference_altitude_m = reference_altitude_m
        self.pipe_length_m = pipe_length_m
        self.pipe_diameter_m = pipe_diameter_m
        self.flow_rate_m3_per_s = flow_rate_m3_per_s
        self.friction_factor = friction_factor
        self.minor_loss_coefficient_k = minor_loss_coefficient_k
        self.safety_margin_percent = safety_margin_percent

    def calculate_required_pressure(
        self,
        zone_altitude_m: float,
        zone_slope_degrees: float,
        base_pressure_kpa: float,
    ) -> Dict[str, float]:
        """
        Calculate required pump pressure for a zone.

        Args:
            zone_altitude_m: Zone altitude in meters (kept for logging / future use).
            zone_slope_degrees: Slope angle θ of the pipe in degrees.
            base_pressure_kpa: Base pressure requirement (emitter / sprinkler spec) in kPa.

        Returns:
            Dictionary with calculated pressure components and metadata.
        """
        # Vertical height head from pipe geometry: h = L · sin(θ)
        height_m = max(
            0.0,
            self.pipe_length_m * math.sin(math.radians(zone_slope_degrees)),
        )
        static_head_kpa = self._calculate_static_head_pressure(height_m)

        # Flow velocity v = Q / A
        velocity_m_per_s = self._calculate_velocity(
            self.flow_rate_m3_per_s, self.pipe_diameter_m
        )

        # Dynamic pressure term (ρ v² / 2) in Pa
        dynamic_pressure_pa = 0.5 * WATER_DENSITY_KG_PER_M3 * velocity_m_per_s ** 2

        # Darcy friction factor f (use configured value if > 0, otherwise estimate)
        friction_factor = (
            self.friction_factor
            if self.friction_factor > 0.0
            else self._estimate_friction_factor(velocity_m_per_s)
        )

        # Friction losses along the pipe: ΔP_fric = f (L/D) (ρ v² / 2)
        friction_loss_kpa = (
            friction_factor
            * (self.pipe_length_m / max(self.pipe_diameter_m, 1e-6))
            * dynamic_pressure_pa
            / 1000.0
        )

        # Minor (local) losses: ΔP_minor = K (ρ v² / 2)
        minor_loss_kpa = (
            self.minor_loss_coefficient_k * dynamic_pressure_pa / 1000.0
        )

        # Sum of all hydraulic requirements before safety margin
        base_plus_losses_kpa = (
            base_pressure_kpa + static_head_kpa + friction_loss_kpa + minor_loss_kpa
        )

        # Apply configurable safety margin
        margin_factor = 1.0 + max(self.safety_margin_percent, 0.0) / 100.0
        total_pressure_kpa = base_plus_losses_kpa * margin_factor
        safety_margin_kpa = total_pressure_kpa - base_plus_losses_kpa

        return {
            # Inputs / geometry
            'base_pressure_kpa': base_pressure_kpa,
            'zone_altitude_m': zone_altitude_m,
            'zone_slope_degrees': zone_slope_degrees,
            'pipe_length_m': self.pipe_length_m,
            'pipe_diameter_m': self.pipe_diameter_m,
            'estimated_flow_rate_m3_per_s': self.flow_rate_m3_per_s,
            'velocity_m_per_s': velocity_m_per_s,
            # Hydraulic components
            'static_head_kpa': static_head_kpa,
            'friction_loss_kpa': friction_loss_kpa,
            'minor_loss_kpa': minor_loss_kpa,
            'darcy_friction_factor': friction_factor,
            # Safety margin
            'safety_margin_percent': self.safety_margin_percent,
            'safety_margin_kpa': safety_margin_kpa,
            # Totals
            'total_required_pressure_kpa': total_pressure_kpa,
            # For compatibility: report the vertical height used for static head
            'altitude_difference_m': height_m,
        }

    def _calculate_static_head_pressure(self, height_m: float) -> float:
        """
        Calculate static head pressure from vertical height.

        P_static = ρ g h   [Pa]  →  kPa
        """
        pressure_pa = WATER_DENSITY_KG_PER_M3 * GRAVITY_M_PER_S2 * height_m
        return pressure_pa / 1000.0

    def _calculate_velocity(self, flow_rate_m3_per_s: float, diameter_m: float) -> float:
        """Calculate mean flow velocity v = Q / A in m/s."""
        if diameter_m <= 0.0:
            return 0.0
        area_m2 = math.pi * (diameter_m ** 2) / 4.0
        if area_m2 <= 0.0:
            return 0.0
        return max(0.0, flow_rate_m3_per_s) / area_m2

    def _estimate_friction_factor(self, velocity_m_per_s: float) -> float:
        """
        Estimate Darcy friction factor f from Reynolds number.

        Uses:
        - Laminar:  f = 64 / Re   for Re < 2300
        - Turbulent (smooth): Blasius: f = 0.3164 / Re^0.25 for Re >= 2300
        """
        if self.pipe_diameter_m <= 0.0 or velocity_m_per_s <= 0.0:
            # Fallback to a conservative default if geometry is invalid
            return 0.03

        reynolds = (
            WATER_DENSITY_KG_PER_M3
            * velocity_m_per_s
            * self.pipe_diameter_m
            / max(WATER_DYNAMIC_VISCOSITY_PA_S, 1e-9)
        )

        if reynolds < 1e-6:
            return 0.03

        if reynolds < 2300.0:
            # Laminar flow
            return max(64.0 / max(reynolds, 1.0), 0.001)

        # Turbulent, smooth pipe (Blasius correlation)
        return max(0.3164 * reynolds ** -0.25, 0.008)

    def calculate_zone_pressure_range(
        self,
        required_pressure_kpa: float,
        tolerance_kpa: float = 10.0,
    ) -> Dict[str, float]:
        """
        Calculate acceptable pressure range for a zone.

        Args:
            required_pressure_kpa: Required pressure in kPa.
            tolerance_kpa: Pressure tolerance in kPa.

        Returns:
            Dictionary with min, max, and target pressure (all in kPa).
        """
        return {
            'target_pressure_kpa': required_pressure_kpa,
            'min_pressure_kpa': max(0.0, required_pressure_kpa - tolerance_kpa),
            'max_pressure_kpa': required_pressure_kpa + tolerance_kpa,
        }

    def update_reference_altitude(self, reference_altitude_m: float):
        """Update reference altitude (retained for API compatibility)."""
        self.reference_altitude_m = reference_altitude_m

