"""Hybrid decision engine combining rule-based and fuzzy inference."""
from typing import Dict, Any
from app.decision_engine.rule_engine import RuleEngine
from app.decision_engine.fuzzy_engine import FuzzyEngine


class HybridEngine:
    """Hybrid engine that combines rule-based and fuzzy outputs."""

    def __init__(self, rule_weight: float = 0.4, fuzzy_weight: float = 0.6):
        """
        Initialize hybrid engine.
        
        Args:
            rule_weight: Weight for rule-based decisions (default: 0.4)
            fuzzy_weight: Weight for fuzzy decisions (default: 0.6)
        """
        self.rule_engine = RuleEngine()
        self.fuzzy_engine = FuzzyEngine()
        self.rule_weight = rule_weight
        self.fuzzy_weight = fuzzy_weight
        
        # Normalize weights
        total_weight = rule_weight + fuzzy_weight
        if total_weight > 0:
            self.rule_weight = rule_weight / total_weight
            self.fuzzy_weight = fuzzy_weight / total_weight

    def should_irrigate(self, soil_moisture_percent: float, weather_condition: str) -> Dict[str, Any]:
        """
        Determine if irrigation should proceed using hybrid approach.
        
        Args:
            soil_moisture_percent: Current soil moisture percentage
            weather_condition: Weather condition ('clear', 'cloudy', 'rainy')
            
        Returns:
            Dictionary with final decision and reasoning
        """
        # Get rule-based decision
        rule_decision = self.rule_engine.should_irrigate(soil_moisture_percent, weather_condition)
        
        # Get fuzzy decision
        fuzzy_decision = self.fuzzy_engine.evaluate_irrigation_need(soil_moisture_percent, weather_condition)
        
        # Combine decisions
        rule_vote = 1.0 if rule_decision['should_irrigate'] else 0.0
        fuzzy_vote = 1.0 if fuzzy_decision['should_irrigate'] else 0.0
        
        weighted_vote = (rule_vote * self.rule_weight) + (fuzzy_vote * self.fuzzy_weight)
        should_irrigate = weighted_vote >= 0.5
        
        # Calculate combined confidence
        rule_confidence = rule_decision.get('confidence', 0.5)
        fuzzy_confidence = fuzzy_decision.get('confidence', 0.5)
        combined_confidence = (rule_confidence * self.rule_weight) + (fuzzy_confidence * self.fuzzy_weight)
        
        # Combine reasons
        reason = f"Hybrid decision: Rule-based ({rule_decision['reason']}) + Fuzzy ({fuzzy_decision['reason']})"
        
        return {
            'should_irrigate': should_irrigate,
            'reason': reason,
            'confidence': combined_confidence,
            'rule_decision': rule_decision,
            'fuzzy_decision': fuzzy_decision,
            'weighted_vote': weighted_vote
        }

    def should_fertigate(self, schedule_triggered: bool = True) -> Dict[str, Any]:
        """
        Determine if fertigation should proceed.
        Fertigation uses only rule-based logic (ignores weather/soil moisture).
        
        Args:
            schedule_triggered: Whether schedule has been triggered
            
        Returns:
            Dictionary with decision
        """
        return self.rule_engine.should_fertigate(schedule_triggered)

    def evaluate_pressure_adjustment(self, current_pressure_kpa: float, target_pressure_kpa: float) -> Dict[str, Any]:
        """
        Evaluate pump pressure adjustment using fuzzy inference.
        
        Args:
            current_pressure_kpa: Current pressure in kPa
            target_pressure_kpa: Target pressure in kPa
            
        Returns:
            Dictionary with pressure adjustment recommendation
        """
        return self.fuzzy_engine.evaluate_pressure_adjustment(current_pressure_kpa, target_pressure_kpa)

    def calculate_irrigation_duration(self, current_moisture: float, target_moisture: float,
                                     area_m2: float, flow_rate_lpm: float) -> float:
        """
        Calculate irrigation duration using rule-based method.
        
        Args:
            current_moisture: Current soil moisture percentage
            target_moisture: Target soil moisture percentage
            area_m2: Area in square meters
            flow_rate_lpm: Flow rate in liters per minute
            
        Returns:
            Estimated duration in seconds
        """
        return self.rule_engine.calculate_irrigation_duration(
            current_moisture, target_moisture, area_m2, flow_rate_lpm
        )

