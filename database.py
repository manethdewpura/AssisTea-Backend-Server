from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json

db = SQLAlchemy()


class WeatherCurrent(db.Model):
    """Model for storing current weather data"""
    __tablename__ = 'weather_current'
    
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.BigInteger, nullable=False, index=True)
    synced_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
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
    sea_level = db.Column(db.Float, nullable=True)
    grnd_level = db.Column(db.Float, nullable=True)
    
    # Wind data
    wind_speed = db.Column(db.Float)
    wind_deg = db.Column(db.Float)
    wind_gust = db.Column(db.Float, nullable=True)
    
    # Other data
    visibility = db.Column(db.Integer)
    clouds_all = db.Column(db.Integer)
    rain_1h = db.Column(db.Float, nullable=True)
    rain_3h = db.Column(db.Float, nullable=True)
    snow_1h = db.Column(db.Float, nullable=True)
    snow_3h = db.Column(db.Float, nullable=True)
    
    # System data
    country = db.Column(db.String(10))
    sunrise = db.Column(db.BigInteger)
    sunset = db.Column(db.BigInteger)
    
    # Store full JSON for flexibility
    raw_data = db.Column(db.Text)
    
    def to_dict(self):
        """Convert model to dictionary"""
        return {
            'id': self.id,
            'timestamp': self.timestamp,
            'synced_at': self.synced_at.isoformat() if self.synced_at else None,
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
                'humidity': self.humidity,
                'sea_level': self.sea_level,
                'grnd_level': self.grnd_level
            },
            'wind': {
                'speed': self.wind_speed,
                'deg': self.wind_deg,
                'gust': self.wind_gust
            },
            'visibility': self.visibility,
            'clouds': {'all': self.clouds_all},
            'rain': {'1h': self.rain_1h, '3h': self.rain_3h} if self.rain_1h or self.rain_3h else None,
            'snow': {'1h': self.snow_1h, '3h': self.snow_3h} if self.snow_1h or self.snow_3h else None,
            'sys': {
                'country': self.country,
                'sunrise': self.sunrise,
                'sunset': self.sunset
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
    city_sunrise = db.Column(db.BigInteger)
    city_sunset = db.Column(db.BigInteger)
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
    sea_level = db.Column(db.Float, nullable=True)
    grnd_level = db.Column(db.Float, nullable=True)
    
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
    snow_1h = db.Column(db.Float, nullable=True)
    snow_3h = db.Column(db.Float, nullable=True)
    
    # Store full JSON for flexibility
    raw_data = db.Column(db.Text)
    
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
                'sunrise': self.city_sunrise,
                'sunset': self.city_sunset,
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
                'humidity': self.humidity,
                'sea_level': self.sea_level,
                'grnd_level': self.grnd_level
            },
            'wind': {
                'speed': self.wind_speed,
                'deg': self.wind_deg,
                'gust': self.wind_gust
            },
            'visibility': self.visibility,
            'clouds': {'all': self.clouds_all},
            'pop': self.pop,
            'rain': {'1h': self.rain_1h, '3h': self.rain_3h} if self.rain_1h or self.rain_3h else None,
            'snow': {'1h': self.snow_1h, '3h': self.snow_3h} if self.snow_1h or self.snow_3h else None
        }


def init_db(app):
    """Initialize the database"""
    with app.app_context():
        db.create_all()
        print("Database initialized successfully")



