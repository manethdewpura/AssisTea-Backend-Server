"""
Background task to automatically check for stale weather data
and generate ML predictions when connection is lost.
Optimized for Raspberry Pi - runs efficiently in background.
"""

import time
import logging
from datetime import datetime, timedelta
from threading import Thread
from flask import Flask
from database import db, WeatherCurrent, WeatherForecast
from ml_predictor import get_predictor, is_ml_available

logger = logging.getLogger(__name__)


class MLBackgroundTask:
    """Background task that monitors weather data and triggers ML predictions"""
    
    def __init__(self, app: Flask, check_interval_seconds: int = 1800):
        """
        Initialize background task
        
        Args:
            app: Flask application instance
            check_interval_seconds: How often to check for stale data (default: 30 minutes)
        """
        self.app = app
        self.check_interval = check_interval_seconds
        self.running = False
        self.thread = None
    
    def _check_and_predict(self):
        """Check if data is stale and generate predictions if needed"""
        with self.app.app_context():
            try:
                # Get latest current weather
                latest_current = WeatherCurrent.query.order_by(
                    WeatherCurrent.timestamp.desc()
                ).first()
                
                if not latest_current:
                    logger.info("No current weather data found, attempting ML prediction...")
                    self._generate_predictions()
                    return
                
                # Check if data is stale (older than 3 hours)
                current_time = datetime.utcnow()
                data_time = datetime.fromtimestamp(latest_current.timestamp / 1000)
                age_hours = (current_time - data_time).total_seconds() / 3600
                
                if age_hours > 3:
                    logger.info(f"Weather data is stale ({age_hours:.2f} hours old), generating ML predictions...")
                    self._generate_predictions()
                else:
                    logger.debug(f"Weather data is fresh ({age_hours:.2f} hours old)")
                    
            except Exception as e:
                logger.error(f"Error in background ML check: {e}", exc_info=True)
    
    def _generate_predictions(self):
        """Generate ML predictions using historical data"""
        try:
            predictor = get_predictor()
            if not predictor:
                logger.warning("ML predictor not available, skipping prediction")
                return
            
            # Get historical data
            historical_forecasts = WeatherForecast.query.order_by(
                WeatherForecast.forecast_dt.asc()
            ).limit(50).all()
            
            latest_current = WeatherCurrent.query.order_by(
                WeatherCurrent.timestamp.desc()
            ).first()
            
            if not historical_forecasts and not latest_current:
                logger.warning("No historical data available for ML prediction")
                return
            
            # Build historical data list
            historical_data = []
            
            for forecast in historical_forecasts:
                historical_data.append({
                    'timestamp': forecast.timestamp,
                    'temp': forecast.temp,
                    'feels_like': forecast.feels_like,
                    'temp_min': forecast.temp_min,
                    'temp_max': forecast.temp_max,
                    'pressure': forecast.pressure,
                    'humidity': forecast.humidity,
                    'wind_speed': forecast.wind_speed,
                    'wind_deg': forecast.wind_deg,
                    'rain_1h': forecast.rain_1h or 0.0,
                    'rain_3h': forecast.rain_3h or 0.0,
                    'clouds_all': forecast.clouds_all or 0,
                })
            
            if latest_current:
                historical_data.append({
                    'timestamp': latest_current.timestamp,
                    'temp': latest_current.temp,
                    'feels_like': latest_current.feels_like,
                    'temp_min': latest_current.temp_min,
                    'temp_max': latest_current.temp_max,
                    'pressure': latest_current.pressure,
                    'humidity': latest_current.humidity,
                    'wind_speed': latest_current.wind_speed,
                    'wind_deg': latest_current.wind_deg,
                    'rain_1h': latest_current.rain_1h or 0.0,
                    'rain_3h': latest_current.rain_3h or 0.0,
                    'clouds_all': latest_current.clouds_all or 0,
                })
            
            if len(historical_data) < 48:
                logger.warning(f"Insufficient historical data: need 48 hours, got {len(historical_data)} records")
                return
            
            # Generate predictions
            predicted_records = predictor.predict(historical_data)
            
            # Get city info
            city_id = None
            city_name = None
            city_country = None
            city_coord_lat = None
            city_coord_lon = None
            
            if historical_forecasts:
                latest_forecast = historical_forecasts[-1]
                city_id = latest_forecast.city_id
                city_name = latest_forecast.city_name
                city_country = latest_forecast.city_country
                city_coord_lat = latest_forecast.city_coord_lat
                city_coord_lon = latest_forecast.city_coord_lon
            elif latest_current:
                city_id = latest_current.location_id
                city_name = latest_current.location_name
                city_coord_lat = latest_current.coord_lat
                city_coord_lon = latest_current.coord_lon
            
            # Store predictions
            timestamp = int(datetime.utcnow().timestamp() * 1000)
            records_created = 0
            
            import json
            for pred_record in predicted_records:
                existing = WeatherForecast.query.filter_by(
                    city_id=city_id,
                    forecast_dt=pred_record['forecast_dt']
                ).first()
                
                if existing:
                    existing.timestamp = timestamp
                    existing.synced_at = datetime.utcnow()
                    existing.forecast_dt_txt = pred_record['forecast_dt_txt']
                    existing.temp = pred_record['temp']
                    existing.feels_like = pred_record['feels_like']
                    existing.temp_min = pred_record['temp_min']
                    existing.temp_max = pred_record['temp_max']
                    existing.pressure = pred_record['pressure']
                    existing.humidity = pred_record['humidity']
                    existing.wind_speed = pred_record['wind_speed']
                    existing.wind_deg = pred_record['wind_deg']
                    existing.rain_1h = pred_record.get('rain_1h', 0.0)
                    existing.rain_3h = pred_record.get('rain_3h', 0.0)
                    existing.clouds_all = pred_record.get('clouds_all', 0)
                    existing.weather_main = pred_record.get('weather_main', 'Clear')
                    existing.weather_description = pred_record.get('weather_description', 'clear sky')
                    existing.weather_icon = pred_record.get('weather_icon', '01d')
                    existing.raw_data = json.dumps({
                        **pred_record,
                        'is_ml_prediction': True,
                        'predicted_at': timestamp
                    })
                else:
                    forecast_record = WeatherForecast(
                        timestamp=timestamp,
                        forecast_dt=pred_record['forecast_dt'],
                        forecast_dt_txt=pred_record['forecast_dt_txt'],
                        city_id=city_id,
                        city_name=city_name,
                        city_country=city_country,
                        city_coord_lat=city_coord_lat,
                        city_coord_lon=city_coord_lon,
                        weather_main=pred_record.get('weather_main', 'Clear'),
                        weather_description=pred_record.get('weather_description', 'clear sky'),
                        weather_icon=pred_record.get('weather_icon', '01d'),
                        temp=pred_record['temp'],
                        feels_like=pred_record['feels_like'],
                        temp_min=pred_record['temp_min'],
                        temp_max=pred_record['temp_max'],
                        pressure=pred_record['pressure'],
                        humidity=pred_record['humidity'],
                        wind_speed=pred_record['wind_speed'],
                        wind_deg=pred_record['wind_deg'],
                        rain_1h=pred_record.get('rain_1h', 0.0),
                        rain_3h=pred_record.get('rain_3h', 0.0),
                        clouds_all=pred_record.get('clouds_all', 0),
                        pop=0.0,
                        raw_data=json.dumps({
                            **pred_record,
                            'is_ml_prediction': True,
                            'predicted_at': timestamp
                        })
                    )
                    db.session.add(forecast_record)
                    records_created += 1
            
            db.session.commit()
            logger.info(f"✓ Background ML prediction: Generated {len(predicted_records)} predictions, "
                       f"{records_created} new records")
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error generating ML predictions in background: {e}", exc_info=True)
    
    def _run(self):
        """Main loop for background task"""
        logger.info(f"ML background task started (check interval: {self.check_interval}s)")
        
        while self.running:
            try:
                self._check_and_predict()
            except Exception as e:
                logger.error(f"Error in background task loop: {e}", exc_info=True)
            
            # Sleep for check interval
            time.sleep(self.check_interval)
        
        logger.info("ML background task stopped")
    
    def start(self):
        """Start the background task"""
        if self.running:
            logger.warning("Background task already running")
            return
        
        self.running = True
        self.thread = Thread(target=self._run, daemon=True)
        self.thread.start()
        logger.info("ML background task started")
    
    def stop(self):
        """Stop the background task"""
        if not self.running:
            return
        
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("ML background task stopped")


# Global background task instance
_background_task: MLBackgroundTask = None


def init_background_task(app: Flask, check_interval_seconds: int = 1800):
    """Initialize and start the background task"""
    global _background_task
    
    if _background_task is None:
        _background_task = MLBackgroundTask(app, check_interval_seconds)
        _background_task.start()
        logger.info("ML background task initialized")
    
    return _background_task


def stop_background_task():
    """Stop the background task"""
    global _background_task
    
    if _background_task:
        _background_task.stop()
        _background_task = None

