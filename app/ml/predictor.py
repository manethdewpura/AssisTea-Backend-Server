"""
ML Weather Prediction Service
Uses 1D CNN model to predict weather when API is unavailable.
Uses full TensorFlow package for both development and Raspberry Pi deployment.
"""

import os
import json
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

# Use full TensorFlow package (both development and Raspberry Pi deployment)
try:
    from tensorflow import lite as tflite
    TENSORFLOW_AVAILABLE = True
    logger.info("Using tensorflow.lite")
except ImportError:
    TENSORFLOW_AVAILABLE = False
    logger.warning("TensorFlow package not available. ML predictions will not work. "
                  "Install with: pip install tensorflow")


class WeatherMLPredictor:
    """Weather prediction using 1D CNN TFLite model"""
    
    def __init__(self, model_path: str, metadata_path: str):
        """
        Initialize the ML predictor
        
        Args:
            model_path: Path to weather_model.tflite
            metadata_path: Path to model_metadata.json
        """
        self.model_path = model_path
        self.metadata_path = metadata_path
        self.interpreter = None
        self.metadata = None
        self.scaler_mean = None
        self.scaler_scale = None
        self.feature_names = None
        self.lookback_hours = 48
        self.prediction_intervals = [3, 6, 9, 12, 15, 18, 21, 24]
        
        if not TENSORFLOW_AVAILABLE:
            raise ImportError("TensorFlow package not available. Install with: pip install tensorflow")
        
        self._load_model()
        self._load_metadata()

    @staticmethod
    def _is_daytime_hour(hour: int) -> bool:
        """Return True if the provided hour is considered daytime."""
        return 6 <= hour < 18

    def _classify_weather_condition(
        self,
        rain_1h: float,
        clouds: int,
        humidity: float,
        wind_speed: float,
        pred_hour: int
    ) -> tuple[str, str, str]:
        """
        Classify weather condition and icon from predicted features.

        Returns:
            Tuple of (weather_main, weather_description, weather_icon)
        """
        icon_suffix = "d" if self._is_daytime_hour(pred_hour) else "n"

        # Prioritize precipitation-related conditions first.
        if rain_1h >= 7.5:
            return "Rain", "heavy rain", f"10{icon_suffix}"
        if rain_1h >= 2.5:
            return "Rain", "moderate rain", f"10{icon_suffix}"
        if rain_1h > 0.5:
            return "Rain", "light rain", f"10{icon_suffix}"
        if rain_1h >= 0.1:
            return "Drizzle", "light drizzle", f"09{icon_suffix}"

        # High humidity + calm wind can indicate low-lying mist/fog.
        if humidity > 95.0 and wind_speed <= 2.0:
            return "Mist", "mist", f"50{icon_suffix}"

        # Refined cloud cover thresholds.
        if clouds >= 85:
            return "Clouds", "overcast clouds", f"04{icon_suffix}"
        if clouds >= 65:
            return "Clouds", "broken clouds", f"04{icon_suffix}"
        if clouds >= 30:
            return "Clouds", "scattered clouds", f"03{icon_suffix}"
        if clouds >= 10:
            return "Clouds", "few clouds", f"02{icon_suffix}"

        return "Clear", "clear sky", f"01{icon_suffix}"

    @staticmethod
    def _estimate_visibility(rain_1h: float, humidity: float) -> int:
        """
        Estimate horizontal visibility (meters) from predicted conditions.
        """
        if humidity > 95.0:
            return 4000
        if rain_1h >= 7.5:
            return 2000
        if rain_1h >= 2.5:
            return 5000
        if rain_1h > 0.1:
            return 7000
        return 10000
    
    def _load_model(self):
        """Load TFLite model"""
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"Model file not found: {self.model_path}")
        
        try:
            self.interpreter = tflite.Interpreter(model_path=self.model_path)
            self.interpreter.allocate_tensors()
            logger.info(f"✓ Loaded TFLite model: {self.model_path}")
        except Exception as e:
            logger.error(f"Failed to load TFLite model: {e}")
            raise
    
    def _load_metadata(self):
        """Load model metadata"""
        if not os.path.exists(self.metadata_path):
            raise FileNotFoundError(f"Metadata file not found: {self.metadata_path}")
        
        with open(self.metadata_path, 'r') as f:
            self.metadata = json.load(f)
        
        # Extract scaler parameters
        scaler_params = self.metadata.get('scaler_params', {})
        self.scaler_mean = np.array(scaler_params.get('mean', []), dtype=np.float32)
        self.scaler_scale = np.array(scaler_params.get('scale', []), dtype=np.float32)
        self.feature_names = scaler_params.get('feature_names', [])
        
        # Extract model config
        model_info = self.metadata.get('model_info', {})
        self.lookback_hours = model_info.get('lookback_hours', 48)
        self.prediction_intervals = model_info.get('prediction_intervals', [3, 6, 9, 12, 15, 18, 21, 24])
        
        logger.info(f"✓ Loaded metadata: {len(self.feature_names)} features, "
                   f"lookback={self.lookback_hours}h, predictions={self.prediction_intervals}")
    
    def _prepare_features_from_db_record(self, record: Dict) -> List[float]:
        """
        Extract features from a database record to match model input format.
        Maps database fields to model features.
        """
        # Get current timestamp
        current_dt = datetime.fromtimestamp(record.get('timestamp', datetime.now().timestamp()) / 1000)
        
        # Extract temporal features
        hour = current_dt.hour
        day_of_year = current_dt.timetuple().tm_yday
        month = current_dt.month
        day_of_week = current_dt.weekday()
        
        # Cyclical encoding
        hour_sin = np.sin(2 * np.pi * hour / 24)
        hour_cos = np.cos(2 * np.pi * hour / 24)
        day_sin = np.sin(2 * np.pi * day_of_year / 365)
        day_cos = np.cos(2 * np.pi * day_of_year / 365)
        month_sin = np.sin(2 * np.pi * month / 12)
        month_cos = np.cos(2 * np.pi * month / 12)
        
        # Time of day indicators
        is_daytime = 1 if 6 <= hour <= 18 else 0
        is_morning = 1 if 6 <= hour < 12 else 0
        is_afternoon = 1 if 12 <= hour < 18 else 0
        is_night = 1 if hour < 6 or hour >= 18 else 0
        
        # Season (meteorological)
        if month in [12, 1, 2]:
            season = 0 
        elif month in [3, 4, 5]:
            season = 1 
        elif month in [6, 7, 8]:
            season = 2 
        else:
            season = 3  
        
        # Calculate dew point (approximation if not available)
        temp = record.get('temp', 25.0)
        humidity = record.get('humidity', 80.0)
        dew_point = temp - ((100 - humidity) / 5)  # Simple approximation
        
        # Build feature vector matching model input order
        features = []
        for feature_name in self.feature_names:
            if feature_name == 'dt':
                features.append(current_dt.timestamp())
            elif feature_name == 'temp':
                features.append(record.get('temp', 25.0))
            elif feature_name == 'dew_point':
                features.append(dew_point)
            elif feature_name == 'feels_like':
                features.append(record.get('feels_like', temp))
            elif feature_name == 'temp_min':
                features.append(record.get('temp_min', temp))
            elif feature_name == 'temp_max':
                features.append(record.get('temp_max', temp))
            elif feature_name == 'pressure':
                features.append(record.get('pressure', 1010.0))
            elif feature_name == 'humidity':
                features.append(record.get('humidity', 80.0))
            elif feature_name == 'wind_speed':
                features.append(record.get('wind_speed', 2.0))
            elif feature_name == 'wind_deg':
                features.append(record.get('wind_deg', 220.0))
            elif feature_name == 'rain_1h':
                features.append(record.get('rain_1h', 0.0))
            elif feature_name == 'rain_3h':
                features.append(record.get('rain_3h', 0.0))
            elif feature_name == 'clouds_all':
                features.append(record.get('clouds_all', 75.0))
            elif feature_name == 'hour':
                features.append(hour)
            elif feature_name == 'day_of_year':
                features.append(day_of_year)
            elif feature_name == 'month':
                features.append(month)
            elif feature_name == 'day_of_week':
                features.append(day_of_week)
            elif feature_name == 'hour_sin':
                features.append(hour_sin)
            elif feature_name == 'hour_cos':
                features.append(hour_cos)
            elif feature_name == 'day_sin':
                features.append(day_sin)
            elif feature_name == 'day_cos':
                features.append(day_cos)
            elif feature_name == 'month_sin':
                features.append(month_sin)
            elif feature_name == 'month_cos':
                features.append(month_cos)
            elif feature_name == 'is_daytime':
                features.append(is_daytime)
            elif feature_name == 'is_morning':
                features.append(is_morning)
            elif feature_name == 'is_afternoon':
                features.append(is_afternoon)
            elif feature_name == 'is_night':
                features.append(is_night)
            elif feature_name == 'season':
                features.append(season)
            else:
                # Default value for unknown features
                features.append(0.0)
        
        return features
    
    def _normalize_features(self, features: np.ndarray) -> np.ndarray:
        """Normalize features using saved scaler parameters"""
        if self.scaler_mean is None or self.scaler_scale is None:
            raise ValueError("Scaler parameters not loaded")
        
        # StandardScaler: (x - mean) / scale
        # Ensure all arrays are float32 to avoid float64 conversion
        features = features.astype(np.float32)
        mean = self.scaler_mean.astype(np.float32)
        scale = self.scaler_scale.astype(np.float32)
        
        normalized = (features - mean) / scale
        return normalized.astype(np.float32)
    
    def _denormalize_predictions(self, predictions: np.ndarray) -> np.ndarray:
        """Denormalize predictions back to original scale"""
        if self.scaler_mean is None or self.scaler_scale is None:
            raise ValueError("Scaler parameters not loaded")
        
        # Inverse transform: (normalized * scale) + mean
        denormalized = (predictions * self.scaler_scale) + self.scaler_mean
        return denormalized
    
    def predict(self, historical_data: List[Dict]) -> List[Dict]:
        """
        Generate weather predictions for next 24 hours (8 time steps at 3h intervals)
        
        Args:
            historical_data: List of weather records (dicts) from database, 
                           ordered by timestamp (oldest first).
                           Should contain at least 48 timesteps.
        
        Returns:
            List of predicted weather records, one for each prediction interval
        """
        # Calculate minimum records needed
        min_records = max(1, self.lookback_hours)
        
        if len(historical_data) < min_records:
            raise ValueError(f"Need at least {min_records} records ({self.lookback_hours} hours), "
                           f"got {len(historical_data)} records")
        
        # Take last N records to match model's lookback_hours
        # Model expects 'lookback_hours' number of timesteps
        lookback_data = historical_data[-self.lookback_hours:]
        
        # Prepare feature matrix
        feature_matrix = []
        for record in lookback_data:
            features = self._prepare_features_from_db_record(record)
            feature_matrix.append(features)
        
        # Convert to numpy array
        X = np.array(feature_matrix, dtype=np.float32)
        
        # Normalize (returns float32)
        X_normalized = self._normalize_features(X)
        
        # Reshape for model input: (1, num_timesteps, num_features)
        # If we have fewer records than lookback_hours, pad with zeros or repeat last
        num_timesteps = len(lookback_data)
        if num_timesteps < self.lookback_hours:
            # Pad with the last record repeated
            padding_needed = self.lookback_hours - num_timesteps
            last_record = X_normalized[-1:]
            padding = np.repeat(last_record, padding_needed, axis=0)
            X_normalized = np.vstack([X_normalized, padding])
        
        X_input = X_normalized.reshape(1, self.lookback_hours, len(self.feature_names))
        
        # Run inference
        input_details = self.interpreter.get_input_details()
        output_details = self.interpreter.get_output_details()
        
        # Ensure input type matches model's expected type (should be float32)
        expected_dtype = input_details[0]['dtype']
        if X_input.dtype != expected_dtype:
            logger.warning(f"Converting input from {X_input.dtype} to {expected_dtype}")
            X_input = X_input.astype(expected_dtype)
        
        # Set input tensor
        self.interpreter.set_tensor(input_details[0]['index'], X_input)
        
        # Invoke
        self.interpreter.invoke()
        
        # Get output
        predictions_normalized = self.interpreter.get_tensor(output_details[0]['index'])
        
        # Denormalize
        predictions = self._denormalize_predictions(predictions_normalized)
        
        # Convert predictions to weather records
        predicted_records = []
        # Anchor prediction horizon to "now" to guarantee next-24h outputs.
        # Do not anchor to latest historical row because it can drift when
        # history includes stale or forecast-derived timestamps.
        base_dt = datetime.now()
        
        for i, interval_hours in enumerate(self.prediction_intervals):
            # Calculate prediction timestamp
            pred_dt = base_dt + timedelta(hours=interval_hours)
            pred_timestamp = int(pred_dt.timestamp() * 1000)
            
            # Extract predicted features
            pred_features = predictions[0, i, :]
            
            # Map features back to weather record format
            feature_dict = dict(zip(self.feature_names, pred_features))
            
            # Determine weather condition based on predicted values
            temp = float(feature_dict.get('temp', 25.0))
            humidity = float(feature_dict.get('humidity', 80.0))
            clouds = int(feature_dict.get('clouds_all', 75.0))
            rain_1h = float(feature_dict.get('rain_1h', 0.0))
            wind_speed = float(feature_dict.get('wind_speed', 2.0))
            weather_main, weather_description, weather_icon = self._classify_weather_condition(
                rain_1h=rain_1h,
                clouds=clouds,
                humidity=humidity,
                wind_speed=wind_speed,
                pred_hour=pred_dt.hour
            )
            visibility = self._estimate_visibility(rain_1h=rain_1h, humidity=humidity)
            
            # Create weather record
            record = {
                'timestamp': pred_timestamp,
                'forecast_dt': int(pred_dt.timestamp()),
                'forecast_dt_txt': pred_dt.strftime('%Y-%m-%d %H:%M:%S'),
                'temp': temp,
                'feels_like': float(feature_dict.get('feels_like', temp)),
                'temp_min': float(feature_dict.get('temp_min', temp)),
                'temp_max': float(feature_dict.get('temp_max', temp)),
                'pressure': float(feature_dict.get('pressure', 1010.0)),
                'humidity': humidity,
                'wind_speed': wind_speed,
                'wind_deg': float(feature_dict.get('wind_deg', 220.0)),
                'rain_1h': rain_1h,
                'rain_3h': float(feature_dict.get('rain_3h', 0.0)),
                'visibility': visibility,
                'clouds_all': clouds,
                'weather_main': weather_main,
                'weather_description': weather_description,
                'weather_icon': weather_icon,
                'is_ml_prediction': True,  # Flag to indicate this is ML predicted
            }
            
            predicted_records.append(record)
        
        logger.info(f"✓ Generated {len(predicted_records)} ML predictions")
        return predicted_records


# Global predictor instance (lazy loaded)
_predictor_instance: Optional[WeatherMLPredictor] = None


def get_predictor() -> Optional[WeatherMLPredictor]:
    """Get or create the global ML predictor instance"""
    global _predictor_instance
    
    if _predictor_instance is None:
        try:
            basedir = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            model_path = os.path.join(basedir, 'models', 'weather_model.tflite')
            metadata_path = os.path.join(basedir, 'models', 'model_metadata.json')
            
            _predictor_instance = WeatherMLPredictor(model_path, metadata_path)
            logger.info("✓ ML Predictor initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize ML Predictor: {e}")
            _predictor_instance = None
    
    return _predictor_instance


def is_ml_available() -> bool:
    """Check if ML prediction is available"""
    return get_predictor() is not None
