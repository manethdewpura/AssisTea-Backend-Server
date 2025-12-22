from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json

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


def init_db(app):
    """Initialize the database"""
    with app.app_context():
        db.create_all()
        print("Database initialized successfully")



