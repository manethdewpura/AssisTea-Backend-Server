"""Machine Learning module for weather prediction"""

from app.ml.predictor import get_predictor, is_ml_available, WeatherMLPredictor
from app.ml.background_task import init_background_task, stop_background_task

__all__ = [
    'get_predictor',
    'is_ml_available',
    'WeatherMLPredictor',
    'init_background_task',
    'stop_background_task'
]
