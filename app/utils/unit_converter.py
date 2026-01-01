"""Unit conversion utilities."""


class UnitConverter:
    """Convert between different units."""

    # Pressure conversion factors (to kPa)
    PRESSURE_CONVERSIONS = {
        'kpa': 1.0,
        'pa': 0.001,
        'bar': 100.0,
        'psi': 6.89476,
        'atm': 101.325,
        'mh2o': 9.80665,  # meters of water column
        'cmh2o': 0.0980665,  # centimeters of water column
    }

    # Length conversion factors (to meters)
    LENGTH_CONVERSIONS = {
        'm': 1.0,
        'cm': 0.01,
        'mm': 0.001,
        'km': 1000.0,
        'ft': 0.3048,
        'in': 0.0254,
    }

    def convert_pressure(self, value: float, from_unit: str, to_unit: str = 'kpa') -> float:
        """
        Convert pressure from one unit to another.
        
        Args:
            value: Pressure value
            from_unit: Source unit
            to_unit: Target unit (default: kPa)
            
        Returns:
            Converted pressure value
        """
        from_unit = from_unit.lower()
        to_unit = to_unit.lower()
        
        if from_unit == to_unit:
            return value
        
        # Convert to kPa first
        if from_unit not in self.PRESSURE_CONVERSIONS:
            raise ValueError(f"Unknown pressure unit: {from_unit}")
        
        value_kpa = value * self.PRESSURE_CONVERSIONS[from_unit]
        
        # Convert from kPa to target unit
        if to_unit not in self.PRESSURE_CONVERSIONS:
            raise ValueError(f"Unknown pressure unit: {to_unit}")
        
        return value_kpa / self.PRESSURE_CONVERSIONS[to_unit]

    def convert_length(self, value: float, from_unit: str, to_unit: str = 'm') -> float:
        """
        Convert length from one unit to another.
        
        Args:
            value: Length value
            from_unit: Source unit
            to_unit: Target unit (default: m)
            
        Returns:
            Converted length value
        """
        from_unit = from_unit.lower()
        to_unit = to_unit.lower()
        
        if from_unit == to_unit:
            return value
        
        # Convert to meters first
        if from_unit not in self.LENGTH_CONVERSIONS:
            raise ValueError(f"Unknown length unit: {from_unit}")
        
        value_m = value * self.LENGTH_CONVERSIONS[from_unit]
        
        # Convert from meters to target unit
        if to_unit not in self.LENGTH_CONVERSIONS:
            raise ValueError(f"Unknown length unit: {to_unit}")
        
        return value_m / self.LENGTH_CONVERSIONS[to_unit]

    def convert_temperature(self, value: float, from_unit: str, to_unit: str = 'celsius') -> float:
        """
        Convert temperature from one unit to another.
        
        Args:
            value: Temperature value
            from_unit: Source unit ('celsius', 'fahrenheit', 'kelvin')
            to_unit: Target unit (default: 'celsius')
            
        Returns:
            Converted temperature value
        """
        from_unit = from_unit.lower()
        to_unit = to_unit.lower()
        
        if from_unit == to_unit:
            return value
        
        # Convert to Celsius first
        if from_unit == 'fahrenheit':
            celsius = (value - 32) * 5 / 9
        elif from_unit == 'kelvin':
            celsius = value - 273.15
        elif from_unit == 'celsius':
            celsius = value
        else:
            raise ValueError(f"Unknown temperature unit: {from_unit}")
        
        # Convert from Celsius to target unit
        if to_unit == 'fahrenheit':
            return celsius * 9 / 5 + 32
        elif to_unit == 'kelvin':
            return celsius + 273.15
        elif to_unit == 'celsius':
            return celsius
        else:
            raise ValueError(f"Unknown temperature unit: {to_unit}")

