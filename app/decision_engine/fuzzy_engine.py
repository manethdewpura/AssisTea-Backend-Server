"""Fuzzy inference engine using scikit-fuzzy."""
import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl
from typing import Dict, Any


class FuzzyEngine:
    """Fuzzy inference system for irrigation decisions."""

    def __init__(self):
        """Initialize fuzzy engine with membership functions and rules."""
        # Input variables
        self.soil_moisture = ctrl.Antecedent(np.arange(0, 101, 1), 'soil_moisture')
        self.weather_condition = ctrl.Antecedent(np.arange(0, 3, 1), 'weather_condition')  # 0=clear, 1=cloudy, 2=rainy
        self.pressure_status = ctrl.Antecedent(np.arange(0, 501, 1), 'pressure_status')  # kPa
        
        # Output variables
        self.irrigation_need = ctrl.Consequent(np.arange(0, 101, 1), 'irrigation_need')
        self.pump_pressure_adjustment = ctrl.Consequent(np.arange(-50, 51, 1), 'pump_pressure_adjustment')
        
        # Membership functions for soil moisture
        self.soil_moisture['dry'] = fuzz.trimf(self.soil_moisture.universe, [0, 0, 40])
        self.soil_moisture['moderate'] = fuzz.trimf(self.soil_moisture.universe, [30, 50, 70])
        self.soil_moisture['wet'] = fuzz.trimf(self.soil_moisture.universe, [60, 100, 100])
        
        # Membership functions for weather condition
        self.weather_condition['clear'] = fuzz.trimf(self.weather_condition.universe, [0, 0, 1])
        self.weather_condition['cloudy'] = fuzz.trimf(self.weather_condition.universe, [0, 1, 2])
        self.weather_condition['rainy'] = fuzz.trimf(self.weather_condition.universe, [1, 2, 2])
        
        # Membership functions for pressure status
        self.pressure_status['low'] = fuzz.trimf(self.pressure_status.universe, [0, 0, 200])
        self.pressure_status['normal'] = fuzz.trimf(self.pressure_status.universe, [150, 250, 350])
        self.pressure_status['high'] = fuzz.trimf(self.pressure_status.universe, [300, 500, 500])
        
        # Membership functions for irrigation need
        self.irrigation_need['low'] = fuzz.trimf(self.irrigation_need.universe, [0, 0, 40])
        self.irrigation_need['medium'] = fuzz.trimf(self.irrigation_need.universe, [30, 50, 70])
        self.irrigation_need['high'] = fuzz.trimf(self.irrigation_need.universe, [60, 100, 100])
        
        # Membership functions for pump pressure adjustment
        self.pump_pressure_adjustment['decrease'] = fuzz.trimf(self.pump_pressure_adjustment.universe, [-50, -50, 0])
        self.pump_pressure_adjustment['maintain'] = fuzz.trimf(self.pump_pressure_adjustment.universe, [-10, 0, 10])
        self.pump_pressure_adjustment['increase'] = fuzz.trimf(self.pump_pressure_adjustment.universe, [0, 50, 50])
        
        # Fuzzy rules
        rule1 = ctrl.Rule(
            self.soil_moisture['dry'] & self.weather_condition['clear'],
            self.irrigation_need['high']
        )
        rule2 = ctrl.Rule(
            self.soil_moisture['moderate'] & self.weather_condition['clear'],
            self.irrigation_need['medium']
        )
        rule3 = ctrl.Rule(
            self.soil_moisture['wet'] | self.weather_condition['rainy'],
            self.irrigation_need['low']
        )
        rule4 = ctrl.Rule(
            self.pressure_status['low'],
            self.pump_pressure_adjustment['increase']
        )
        rule5 = ctrl.Rule(
            self.pressure_status['normal'],
            self.pump_pressure_adjustment['maintain']
        )
        rule6 = ctrl.Rule(
            self.pressure_status['high'],
            self.pump_pressure_adjustment['decrease']
        )
        
        # Control system
        self.irrigation_ctrl = ctrl.ControlSystem([rule1, rule2, rule3])
        self.pressure_ctrl = ctrl.ControlSystem([rule4, rule5, rule6])
        
        self.irrigation_sim = ctrl.ControlSystemSimulation(self.irrigation_ctrl)
        self.pressure_sim = ctrl.ControlSystemSimulation(self.pressure_ctrl)

    def evaluate_irrigation_need(self, soil_moisture_percent: float, weather_condition: str) -> Dict[str, Any]:
        """
        Evaluate irrigation need using fuzzy inference.
        
        Args:
            soil_moisture_percent: Soil moisture percentage (0-100)
            weather_condition: Weather condition ('clear', 'cloudy', 'rainy')
            
        Returns:
            Dictionary with irrigation need score and decision
        """
        # Map weather condition to numeric value
        weather_map = {'clear': 0, 'cloudy': 1, 'rainy': 2}
        weather_value = weather_map.get(weather_condition.lower(), 1)
        
        # Set input values
        self.irrigation_sim.input['soil_moisture'] = max(0, min(100, soil_moisture_percent))
        self.irrigation_sim.input['weather_condition'] = weather_value
        
        # Compute
        try:
            self.irrigation_sim.compute()
            irrigation_need_score = self.irrigation_sim.output['irrigation_need']
        except Exception as e:
            # Fallback to default
            irrigation_need_score = 50.0
        
        # Determine decision (threshold at 50)
        # Convert numpy bool to Python bool for JSON serialization
        should_irrigate = bool(irrigation_need_score >= 50.0)
        
        return {
            'irrigation_need_score': float(irrigation_need_score),
            'should_irrigate': should_irrigate,
            'confidence': float(abs(irrigation_need_score - 50) / 50.0),  # Normalize to 0-1
            'reason': f'Fuzzy inference: irrigation need score = {irrigation_need_score:.1f}'
        }

    def evaluate_pressure_adjustment(self, current_pressure_kpa: float, target_pressure_kpa: float) -> Dict[str, Any]:
        """
        Evaluate pump pressure adjustment using fuzzy inference.
        
        Args:
            current_pressure_kpa: Current pressure in kPa
            target_pressure_kpa: Target pressure in kPa
            
        Returns:
            Dictionary with pressure adjustment recommendation
        """
        # Use current pressure as input
        pressure_value = max(0, min(500, current_pressure_kpa))
        
        # Set input value
        self.pressure_sim.input['pressure_status'] = pressure_value
        
        # Compute
        try:
            self.pressure_sim.compute()
            adjustment = self.pressure_sim.output['pump_pressure_adjustment']
        except Exception as e:
            # Fallback: calculate simple difference
            adjustment = target_pressure_kpa - current_pressure_kpa
        
        # Calculate recommended pressure
        recommended_pressure = current_pressure_kpa + adjustment
        
        return {
            'adjustment_kpa': float(adjustment),
            'recommended_pressure_kpa': float(recommended_pressure),
            'current_pressure_kpa': float(current_pressure_kpa),
            'target_pressure_kpa': float(target_pressure_kpa)
        }

