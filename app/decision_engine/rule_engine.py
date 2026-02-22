"""Rule-based decision engine."""
from typing import Dict, Any, Optional
from app.config.config import ADEQUATE_SOIL_MOISTURE_PERCENT


class RuleEngine:
    """Rule-based logic for irrigation/fertigation decisions."""

    def __init__(self):
        """Initialize rule engine."""
        pass

    def should_irrigate(self, soil_moisture_percent: float, weather_condition: str) -> Dict[str, Any]:
        """
        Determine if irrigation should proceed based on rules.
        
        Args:
            soil_moisture_percent: Current soil moisture percentage
            weather_condition: Weather condition ('clear', 'cloudy', 'rainy')
            
        Returns:
            Dictionary with decision and reasoning
        """
        decision = {
            'should_irrigate': False,
            'reason': '',
            'confidence': 0.0
        }
        
        # Rule 1: Skip if weather is not clear
        if weather_condition != 'clear':
            decision['should_irrigate'] = False
            weather_display = weather_condition.capitalize()
            decision['reason'] = f'Weather is {weather_display.lower()}. Irrigation is not recommended in {weather_display.lower()} conditions.'
            decision['user_message'] = f'Irrigation skipped: Weather is {weather_display.lower()}'
            decision['confidence'] = 1.0
            return decision
        
        # Rule 2: Skip if soil moisture is adequate
        if soil_moisture_percent >= ADEQUATE_SOIL_MOISTURE_PERCENT:
            decision['should_irrigate'] = False
            decision['reason'] = f'Soil moisture is adequate at {soil_moisture_percent:.1f}% (target: {ADEQUATE_SOIL_MOISTURE_PERCENT}%)'
            decision['user_message'] = f'Irrigation skipped: Soil moisture is adequate ({soil_moisture_percent:.1f}%)'
            decision['confidence'] = 1.0
            return decision
        
        # Rule 3: Irrigate if moisture is below adequate level and weather is clear
        if soil_moisture_percent < ADEQUATE_SOIL_MOISTURE_PERCENT:
            decision['should_irrigate'] = True
            decision['reason'] = f'Soil moisture {soil_moisture_percent:.1f}% is below adequate level ({ADEQUATE_SOIL_MOISTURE_PERCENT}%) and weather is clear'
            decision['confidence'] = 1.0
            return decision
        
        return decision

    def should_fertigate(self, schedule_triggered: bool = True) -> Dict[str, Any]:
        """
        Determine if fertigation should proceed.
        Note: Fertigation ignores weather and soil moisture per requirements.
        
        Args:
            schedule_triggered: Whether schedule has been triggered
            
        Returns:
            Dictionary with decision and reasoning
        """
        decision = {
            'should_fertigate': schedule_triggered,
            'reason': 'Fertigation scheduled' if schedule_triggered else 'No schedule triggered',
            'confidence': 1.0
        }
        
        return decision

    def calculate_irrigation_duration(self, current_moisture: float, target_moisture: float,
                                     area_m2: float, flow_rate_lpm: float) -> float:
        """
        Estimate irrigation duration based on moisture deficit.
        
        Args:
            current_moisture: Current soil moisture percentage
            target_moisture: Target soil moisture percentage
            area_m2: Area in square meters
            flow_rate_lpm: Flow rate in liters per minute
            
        Returns:
            Estimated duration in seconds
        """
        # Simplified calculation: assume 1% moisture = 1mm water depth
        moisture_deficit = target_moisture - current_moisture
        if moisture_deficit <= 0:
            return 0.0
        
        # Convert area to liters needed (1mm = 1L per m²)
        water_needed_liters = (moisture_deficit / 100.0) * area_m2 * 10  # 10mm per 1% moisture
        
        # Calculate duration
        if flow_rate_lpm <= 0:
            return 0.0
        
        duration_minutes = water_needed_liters / flow_rate_lpm
        return duration_minutes * 60.0  # Convert to seconds

