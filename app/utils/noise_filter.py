"""Noise filtering utilities for sensor data."""
from collections import deque
from typing import List
import statistics


class NoiseFilter:
    """Filter noise from sensor readings using various techniques."""

    def __init__(self, window_size: int = 5, method: str = 'moving_average'):
        """
        Initialize noise filter.
        
        Args:
            window_size: Size of the moving window
            method: Filtering method ('moving_average', 'median', 'outlier_removal')
        """
        self.window_size = window_size
        self.method = method
        self.readings: deque = deque(maxlen=window_size)

    def filter(self, value: float) -> float:
        """
        Filter a single value.
        
        Args:
            value: Raw sensor reading
            
        Returns:
            Filtered value
        """
        self.readings.append(value)
        
        if len(self.readings) < 2:
            return value
        
        if self.method == 'moving_average':
            return self._moving_average()
        elif self.method == 'median':
            return self._median_filter()
        elif self.method == 'outlier_removal':
            return self._outlier_removal()
        else:
            return value

    def _moving_average(self) -> float:
        """Calculate moving average."""
        return sum(self.readings) / len(self.readings)

    def _median_filter(self) -> float:
        """Calculate median value."""
        return statistics.median(self.readings)

    def _outlier_removal(self) -> float:
        """
        Remove outliers using IQR method and return mean.
        """
        if len(self.readings) < 3:
            return statistics.mean(self.readings)
        
        sorted_readings = sorted(self.readings)
        q1_index = len(sorted_readings) // 4
        q3_index = (3 * len(sorted_readings)) // 4
        
        q1 = sorted_readings[q1_index]
        q3 = sorted_readings[q3_index]
        iqr = q3 - q1
        
        # Filter outliers (values outside Q1 - 1.5*IQR and Q3 + 1.5*IQR)
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        
        filtered = [r for r in self.readings if lower_bound <= r <= upper_bound]
        
        if len(filtered) == 0:
            return statistics.mean(self.readings)
        
        return statistics.mean(filtered)

    def reset(self):
        """Reset filter state."""
        self.readings.clear()

