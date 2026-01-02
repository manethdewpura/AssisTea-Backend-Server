from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class WeatherCurrent(db.Model):
    """Model for storing current weather data"""
    __tablename__ = 'weather_current'
    
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.BigInteger, nullable=False, index=True)  # Sync timestamp (when data was sent to backend)
    synced_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)  # When record was saved to database
    measured_at = db.Column(db.BigInteger, nullable=True, index=True)  # Actual weather measurement time (dt from API)
    
    # Location data
    coord_lon = db.Column(db.Float, nullable=False)
    coord_lat = db.Column(db.Float, nullable=False)
    location_name = db.Column(db.String(200))
    location_id = db.Column(db.Integer)
    timezone = db.Column(db.Integer)
    
    # Weather conditions
    weather_main = db.Column(db.String(100))
    weather_description = db.Column(db.String(200))
    weather_icon = db.Column(db.String(50))
    
    # Main weather data
    temp = db.Column(db.Float)
    feels_like = db.Column(db.Float)
    temp_min = db.Column(db.Float)
    temp_max = db.Column(db.Float)
    pressure = db.Column(db.Float)
    humidity = db.Column(db.Float)
    
    # Wind data
    wind_speed = db.Column(db.Float)
    wind_deg = db.Column(db.Float)
    wind_gust = db.Column(db.Float, nullable=True)
    
    # Other data
    visibility = db.Column(db.Integer)
    clouds_all = db.Column(db.Integer)
    rain_1h = db.Column(db.Float, nullable=True)
    rain_3h = db.Column(db.Float, nullable=True)
    
    # System data
    country = db.Column(db.String(10))
    
    # Data tracking and ML prediction metadata
    data_source = db.Column(db.String(50), default='api', nullable=False)  # 'api', 'ml_prediction', 'forecast_derived'
    is_ml_generated = db.Column(db.Boolean, default=False, nullable=False, index=True)  # Flag for ML predictions
    confidence_score = db.Column(db.Float, default=1.0)  # Confidence: 1.0 (API) to 0.0 (low confidence)
    
    # Store full JSON for flexibility
    raw_data = db.Column(db.Text)
    
    # Unique constraint: prevent duplicate records for same location and measurement time
    __table_args__ = (
        db.UniqueConstraint('location_id', 'measured_at', name='uix_location_measured_at'),
    )
    
    def to_dict(self):
        """Convert model to dictionary"""
        return {
            'id': self.id,
            'timestamp': self.timestamp,  # Sync timestamp
            'synced_at': self.synced_at.isoformat() if self.synced_at else None,  # Database save time
            'measured_at': self.measured_at,  # Actual weather measurement time (dt from API)
            'coord': {'lon': self.coord_lon, 'lat': self.coord_lat},
            'location_name': self.location_name,
            'location_id': self.location_id,
            'timezone': self.timezone,
            'weather': {
                'main': self.weather_main,
                'description': self.weather_description,
                'icon': self.weather_icon
            },
            'main': {
                'temp': self.temp,
                'feels_like': self.feels_like,
                'temp_min': self.temp_min,
                'temp_max': self.temp_max,
                'pressure': self.pressure,
                'humidity': self.humidity
            },
            'wind': {
                'speed': self.wind_speed,
                'deg': self.wind_deg,
                'gust': self.wind_gust
            },
            'visibility': self.visibility,
            'clouds': {'all': self.clouds_all},
            'rain': {'1h': self.rain_1h, '3h': self.rain_3h} if self.rain_1h or self.rain_3h else None,
            'sys': {
                'country': self.country
            }
        }


class WeatherForecast(db.Model):
    """Model for storing weather forecast data"""
    __tablename__ = 'weather_forecast'
    
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.BigInteger, nullable=False, index=True)
    synced_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # City information
    city_id = db.Column(db.Integer)
    city_name = db.Column(db.String(200))
    city_country = db.Column(db.String(10))
    city_coord_lat = db.Column(db.Float)
    city_coord_lon = db.Column(db.Float)
    city_timezone = db.Column(db.Integer)
    city_population = db.Column(db.Integer)
    
    # Forecast item data
    forecast_dt = db.Column(db.BigInteger, nullable=False, index=True)
    forecast_dt_txt = db.Column(db.String(50))
    
    # Weather conditions
    weather_main = db.Column(db.String(100))
    weather_description = db.Column(db.String(200))
    weather_icon = db.Column(db.String(50))
    
    # Main weather data
    temp = db.Column(db.Float)
    feels_like = db.Column(db.Float)
    temp_min = db.Column(db.Float)
    temp_max = db.Column(db.Float)
    pressure = db.Column(db.Float)
    humidity = db.Column(db.Float)
    
    # Wind data
    wind_speed = db.Column(db.Float)
    wind_deg = db.Column(db.Float)
    wind_gust = db.Column(db.Float, nullable=True)
    
    # Other data
    visibility = db.Column(db.Integer)
    clouds_all = db.Column(db.Integer)
    pop = db.Column(db.Float)  # Probability of precipitation
    rain_1h = db.Column(db.Float, nullable=True)
    rain_3h = db.Column(db.Float, nullable=True)
    
    # Store full JSON for flexibility
    raw_data = db.Column(db.Text)
    
    # Unique constraint: prevent duplicate forecasts for same city and forecast time
    __table_args__ = (
        db.UniqueConstraint('city_id', 'forecast_dt', name='uix_city_forecast_dt'),
    )
    
    def to_dict(self):
        """Convert model to dictionary"""
        return {
            'id': self.id,
            'timestamp': self.timestamp,
            'synced_at': self.synced_at.isoformat() if self.synced_at else None,
            'forecast_dt': self.forecast_dt,
            'forecast_dt_txt': self.forecast_dt_txt,
            'city': {
                'id': self.city_id,
                'name': self.city_name,
                'country': self.city_country,
                'coord': {'lat': self.city_coord_lat, 'lon': self.city_coord_lon},
                'timezone': self.city_timezone,
                'population': self.city_population
            },
            'weather': {
                'main': self.weather_main,
                'description': self.weather_description,
                'icon': self.weather_icon
            },
            'main': {
                'temp': self.temp,
                'feels_like': self.feels_like,
                'temp_min': self.temp_min,
                'temp_max': self.temp_max,
                'pressure': self.pressure,
                'humidity': self.humidity
            },
            'wind': {
                'speed': self.wind_speed,
                'deg': self.wind_deg,
                'gust': self.wind_gust
            },
            'visibility': self.visibility,
            'clouds': {'all': self.clouds_all},
            'pop': self.pop,
            'rain': {'1h': self.rain_1h, '3h': self.rain_3h} if self.rain_1h or self.rain_3h else None
        }


def build_historical_data_for_prediction(lookback_hours: int = 48, city_id: int = None):
    """
    Build historical weather data for ML prediction using both weather_current and weather_forecast tables.
    This hybrid approach ensures predictions can be made even during extended connection loss.
    
    Strategy:
    1. First, try to get data from weather_current (actual measured data - preferred)
    2. If insufficient, supplement with weather_forecast data:
       - Use forecast records that are in the past (already happened) - most accurate
       - If still insufficient, use most recent forecast records closest to "now"
    
    Args:
        lookback_hours: Number of hours of historical data needed (default: 48)
        city_id: Optional city_id to filter by location
    
    Returns:
        Tuple of (historical_data_list, city_info_dict, data_source_info)
        - historical_data_list: List of dicts with weather data, ordered by timestamp (oldest first)
        - city_info_dict: Dict with city information (id, name, country, coords)
        - data_source_info: Dict with info about data sources used
    """
    from datetime import datetime, timedelta
    
    current_time = datetime.utcnow()
    cutoff_timestamp = int((current_time - timedelta(hours=lookback_hours)).timestamp() * 1000)
    cutoff_timestamp_seconds = int((current_time - timedelta(hours=lookback_hours)).timestamp())
    current_timestamp_seconds = int(current_time.timestamp())
    
    historical_data = []
    city_info = {}
    data_source_info = {
        'current_count': 0,
        'forecast_count': 0,
        'has_sufficient_data': False
    }
    
    # Step 1: Get data from weather_current (actual measured data - preferred)
    query_current = WeatherCurrent.query
    if city_id is not None:
        query_current = query_current.filter_by(location_id=city_id)
    
    historical_current = query_current.filter(
        WeatherCurrent.measured_at >= cutoff_timestamp
    ).order_by(WeatherCurrent.measured_at.asc()).all()
    
    # Build list from current weather data
    for current in historical_current:
        historical_data.append({
            'timestamp': current.measured_at or current.timestamp,
            'temp': current.temp,
            'feels_like': current.feels_like,
            'temp_min': current.temp_min,
            'temp_max': current.temp_max,
            'pressure': current.pressure,
            'humidity': current.humidity,
            'wind_speed': current.wind_speed,
            'wind_deg': current.wind_deg,
            'rain_1h': current.rain_1h or 0.0,
            'rain_3h': current.rain_3h or 0.0,
            'clouds_all': current.clouds_all or 0,
            'source': 'current'  # Mark data source
        })
        
        # Store city info from first record
        if not city_info:
            city_info = {
                'id': current.location_id,
                'name': current.location_name,
                'country': current.country or '',
                'coord_lat': current.coord_lat,
                'coord_lon': current.coord_lon
            }
    
    data_source_info['current_count'] = len(historical_data)
    
    # Step 2: If insufficient data, supplement with weather_forecast
    if len(historical_data) < lookback_hours:
        needed_records = lookback_hours - len(historical_data)
        
        query_forecast = WeatherForecast.query
        if city_id is not None:
            query_forecast = query_forecast.filter_by(city_id=city_id)
        
        # Strategy 2a: Get forecast records that are in the past (already happened)
        # These are the most accurate since they were predictions that have now occurred
        past_forecasts = query_forecast.filter(
            WeatherForecast.forecast_dt <= current_timestamp_seconds,
            WeatherForecast.forecast_dt >= cutoff_timestamp_seconds
        ).order_by(WeatherForecast.forecast_dt.desc()).limit(needed_records).all()
        
        # Convert forecast records to historical data format
        forecast_data_list = []
        for forecast in past_forecasts:
            # Convert forecast_dt (Unix timestamp in seconds) to milliseconds for consistency
            forecast_timestamp_ms = forecast.forecast_dt * 1000
            forecast_data_list.append({
                'timestamp': forecast_timestamp_ms,
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
                'source': 'forecast_past'  # Mark as past forecast data
            })
            
            # Store city info if not already set
            if not city_info:
                city_info = {
                    'id': forecast.city_id,
                    'name': forecast.city_name,
                    'country': forecast.city_country or '',
                    'coord_lat': forecast.city_coord_lat,
                    'coord_lon': forecast.city_coord_lon
                }
        
        # Strategy 2b: If still insufficient, use most recent forecast records (even if future)
        # These are from the last API call before connection loss
        if len(forecast_data_list) < needed_records:
            remaining_needed = needed_records - len(forecast_data_list)
            
            # Get the most recent forecast data (closest to "now")
            # This uses the last API call's forecast data as historical input
            recent_forecasts = query_forecast.filter(
                WeatherForecast.forecast_dt >= cutoff_timestamp_seconds
            ).order_by(WeatherForecast.forecast_dt.asc()).limit(remaining_needed).all()
            
            for forecast in recent_forecasts:
                forecast_timestamp_ms = forecast.forecast_dt * 1000
                forecast_data_list.append({
                    'timestamp': forecast_timestamp_ms,
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
                    'source': 'forecast_recent'  # Mark as recent forecast data
                })
                
                if not city_info:
                    city_info = {
                        'id': forecast.city_id,
                        'name': forecast.city_name,
                        'country': forecast.city_country or '',
                        'coord_lat': forecast.city_coord_lat,
                        'coord_lon': forecast.city_coord_lon
                    }
        
        # Merge forecast data with current data, ensuring chronological order
        historical_data.extend(forecast_data_list)
        data_source_info['forecast_count'] = len(forecast_data_list)
    
    # Step 3: Use ML-generated predictions from weather_current (Recursive Prediction)
    # This enables self-sustaining predictions during extreme connection loss
    if len(historical_data) < lookback_hours:
        needed_records = lookback_hours - len(historical_data)
        
        query_ml = WeatherCurrent.query
        if city_id is not None:
            query_ml = query_ml.filter_by(location_id=city_id)
        
        # Get ML-generated records that are within our lookback window
        ml_predictions = query_ml.filter(
            WeatherCurrent.is_ml_generated == True,
            WeatherCurrent.measured_at >= cutoff_timestamp
        ).order_by(WeatherCurrent.measured_at.asc()).limit(needed_records).all()
        
        ml_count = 0
        for ml_record in ml_predictions:
            historical_data.append({
                'timestamp': ml_record.measured_at or ml_record.timestamp,
                'temp': ml_record.temp,
                'feels_like': ml_record.feels_like,
                'temp_min': ml_record.temp_min,
                'temp_max': ml_record.temp_max,
                'pressure': ml_record.pressure,
                'humidity': ml_record.humidity,
                'wind_speed': ml_record.wind_speed,
                'wind_deg': ml_record.wind_deg,
                'rain_1h': ml_record.rain_1h or 0.0,
                'rain_3h': ml_record.rain_3h or 0.0,
                'clouds_all': ml_record.clouds_all or 0,
                'source': 'ml_prediction'  # Mark as ML-generated data
            })
            ml_count += 1
            
            if not city_info:
                city_info = {
                    'id': ml_record.location_id,
                    'name': ml_record.location_name,
                    'country': ml_record.country or '',
                    'coord_lat': ml_record.coord_lat,
                    'coord_lon': ml_record.coord_lon
                }
        
        data_source_info['ml_prediction_count'] = ml_count
        
        # Sort all data by timestamp (oldest first)
        historical_data.sort(key=lambda x: x['timestamp'])
        
        # Remove duplicates (same timestamp) - prefer 'current' over 'forecast' over 'ml_prediction'
        seen_timestamps = {}
        source_priority = {'current': 3, 'forecast_past': 2, 'forecast_recent': 1, 'ml_prediction': 0}
        
        for record in historical_data:
            # Use exact timestamp - only deduplicate if timestamps are exactly the same
            timestamp = record['timestamp']
            if timestamp not in seen_timestamps:
                seen_timestamps[timestamp] = record
            else:
                # Replace with higher priority source if available
                current_priority = source_priority.get(record['source'], 0)
                existing_priority = source_priority.get(seen_timestamps[timestamp]['source'], 0)
                if current_priority > existing_priority:
                    seen_timestamps[timestamp] = record
        
        # Build deduplicated list from dictionary values (already unique by timestamp)
        historical_data = sorted(seen_timestamps.values(), key=lambda x: x['timestamp'])
    else:
        # No ML predictions used
        data_source_info['ml_prediction_count'] = 0
        
        # Sort all data by timestamp (oldest first)
        historical_data.sort(key=lambda x: x['timestamp'])
        
        # Remove duplicates (same timestamp) - prefer 'current' over 'forecast'
        seen_timestamps = {}
        for record in historical_data:
            # Use exact timestamp - only deduplicate if timestamps are exactly the same
            timestamp = record['timestamp']
            if timestamp not in seen_timestamps:
                seen_timestamps[timestamp] = record
            elif record['source'] == 'current' and seen_timestamps[timestamp]['source'] != 'current':
                # Replace forecast with current if available
                seen_timestamps[timestamp] = record
        
        # Build deduplicated list from dictionary values (already unique by timestamp)
        historical_data = sorted(seen_timestamps.values(), key=lambda x: x['timestamp'])
    
    # Take last N hours worth of data (ensuring we have exactly what we need)
    # With hourly API calls, we need lookback_hours records (1 record per hour)
    target_records = lookback_hours  # For 48 hours with hourly data = 48 records
    
    if len(historical_data) > target_records:
        historical_data = historical_data[-target_records:]
    
    # Remove 'source' field before returning (not needed for ML model)
    for record in historical_data:
        record.pop('source', None)
    
    data_source_info['has_sufficient_data'] = len(historical_data) >= lookback_hours  # Need full lookback period
    
    return historical_data, city_info, data_source_info


def init_db(app):
    """Initialize the database"""
    with app.app_context():
        db.create_all()
        print("Database initialized successfully")



