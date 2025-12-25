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
from database import db, WeatherCurrent, WeatherForecast, build_historical_data_for_prediction
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
        """Generate ML predictions using historical weather data from both weather_current and weather_forecast tables"""
        try:
            predictor = get_predictor()
            if not predictor:
                logger.warning("ML predictor not available, skipping prediction")
                return
            
            # Get city_id from latest current weather (if available) for filtering
            latest_current = WeatherCurrent.query.order_by(WeatherCurrent.timestamp.desc()).first()
            city_id = latest_current.location_id if latest_current else None
            
            # Build historical data using hybrid approach (current + forecast)
            historical_data, city_info, data_source_info = build_historical_data_for_prediction(
                lookback_hours=predictor.lookback_hours,
                city_id=city_id
            )
            
            if not data_source_info['has_sufficient_data']:
                logger.warning(
                    f"Insufficient historical data: need at least 48 hours ({predictor.lookback_hours} hours), "
                    f"got {len(historical_data)} records. "
                    f"Sources: {data_source_info['current_count']} from current, "
                    f"{data_source_info['forecast_count']} from forecast"
                )
                return
            
            logger.info(
                f"Building prediction input: {len(historical_data)} records "
                f"({data_source_info['current_count']} from current, "
                f"{data_source_info['forecast_count']} from forecast)"
            )
            
            # Ensure we have exactly the right amount of data
            if len(historical_data) > predictor.lookback_hours:
                historical_data = historical_data[-predictor.lookback_hours:]
            
            # Generate predictions
            predicted_records = predictor.predict(historical_data)
            
            # Get city info from helper function result or fallback to latest current
            if city_info:
                city_id = city_info['id']
                city_name = city_info['name']
                city_country = city_info['country']
                city_coord_lat = city_info['coord_lat']
                city_coord_lon = city_info['coord_lon']
            elif latest_current:
                city_id = latest_current.location_id
                city_name = latest_current.location_name
                city_country = latest_current.country or ''
                city_coord_lat = latest_current.coord_lat
                city_coord_lon = latest_current.coord_lon
            else:
                logger.error("No city information available for predictions")
                return
            
            # Store predictions in both weather_forecast AND weather_current tables
            timestamp = int(datetime.utcnow().timestamp() * 1000)
            forecast_records_created = 0
            current_records_created = 0
            
            # Calculate confidence score based on data sources used
            # API data: 1.0, Real+Forecast: 0.75, With ML predictions: 0.55
            base_confidence = 1.0
            if data_source_info['forecast_count'] > 0:
                base_confidence = 0.75
            if data_source_info.get('ml_prediction_count', 0) > 0:
                base_confidence = 0.55
            
            import json
            for pred_record in predicted_records:
                # 1. Store in weather_forecast table (existing behavior)
                existing_forecast = WeatherForecast.query.filter_by(
                    city_id=city_id,
                    forecast_dt=pred_record['forecast_dt']
                ).first()
                
                if existing_forecast:
                    existing_forecast.timestamp = timestamp
                    existing_forecast.synced_at = datetime.utcnow()
                    existing_forecast.forecast_dt_txt = pred_record['forecast_dt_txt']
                    existing_forecast.temp = pred_record['temp']
                    existing_forecast.feels_like = pred_record['feels_like']
                    existing_forecast.temp_min = pred_record['temp_min']
                    existing_forecast.temp_max = pred_record['temp_max']
                    existing_forecast.pressure = pred_record['pressure']
                    existing_forecast.humidity = pred_record['humidity']
                    existing_forecast.wind_speed = pred_record['wind_speed']
                    existing_forecast.wind_deg = pred_record['wind_deg']
                    existing_forecast.rain_1h = pred_record.get('rain_1h', 0.0)
                    existing_forecast.rain_3h = pred_record.get('rain_3h', 0.0)
                    existing_forecast.clouds_all = pred_record.get('clouds_all', 0)
                    existing_forecast.weather_main = pred_record.get('weather_main', 'Clear')
                    existing_forecast.weather_description = pred_record.get('weather_description', 'clear sky')
                    existing_forecast.weather_icon = pred_record.get('weather_icon', '01d')
                    existing_forecast.raw_data = json.dumps({
                        **pred_record,
                        'is_ml_prediction': True,
                        'predicted_at': timestamp,
                        'confidence_score': base_confidence
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
                            'predicted_at': timestamp,
                            'confidence_score': base_confidence
                        })
                    )
                    db.session.add(forecast_record)
                    forecast_records_created += 1
                
                # 2. Store in weather_current table (NEW - enables recursive prediction)
                # This allows future ML predictions to use previous ML predictions as input
                existing_current = WeatherCurrent.query.filter_by(
                    location_id=city_id,
                    measured_at=pred_record['timestamp']
                ).first()
                
                if not existing_current:
                    current_record = WeatherCurrent(
                        timestamp=timestamp,
                        synced_at=datetime.utcnow(),
                        measured_at=pred_record['timestamp'],
                        coord_lon=city_coord_lon,
                        coord_lat=city_coord_lat,
                        location_name=city_name,
                        location_id=city_id,
                        country=city_country,
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
                        visibility=10000,  # Default visibility
                        # ML tracking fields
                        data_source='ml_prediction',
                        is_ml_generated=True,
                        confidence_score=base_confidence,
                        raw_data=json.dumps({
                            **pred_record,
                            'is_ml_prediction': True,
                            'predicted_at': timestamp,
                            'confidence_score': base_confidence
                        })
                    )
                    db.session.add(current_record)
                    current_records_created += 1
            
            db.session.commit()
            logger.info(
                f"✓ Background ML prediction: Generated {len(predicted_records)} predictions "
                f"(Confidence: {base_confidence:.2f}), "
                f"created {forecast_records_created} forecast records, "
                f"{current_records_created} current records for recursive prediction"
            )
            
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

