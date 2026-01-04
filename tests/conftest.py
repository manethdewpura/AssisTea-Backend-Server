"""Shared pytest fixtures for testing."""
import pytest
import os
import tempfile
import shutil
from unittest.mock import patch
from flask import Flask
from app.hardware.mock_gpio import MockGPIO
from app.hardware.ads1115_adc import ADS1115ADC
from app.sensors.soil_moisture import SoilMoistureSensor
from app.sensors.pressure import PressureSensor
from app.sensors.tank_level import TankLevelSensor
from app.sensors.weather import WeatherReader
from app.hydraulics.pressure_calculator import PressureCalculator
from app.hydraulics.valve_controller import HydraulicValveController
from app.hydraulics.pump_controller import HydraulicPumpController
from app.decision_engine.hybrid_engine import HybridEngine
from app.controllers.irrigation_controller import IrrigationController
from app.controllers.fertigation_controller import FertigationController
from app.hardware.pump_interface import SimplePumpController
from app.hardware.valve_interface import SolenoidValveController
from app.hardware.tank_valve_controller import TankValveController
from app.config.config import (
    PUMP_GPIO_PIN, TANK_INLET_SOLENOID_PIN, TANK_OUTLET_SOLENOID_PIN,
    DEFAULT_TANK_LEVEL_TRIGGER_PIN, DEFAULT_TANK_LEVEL_ECHO_PIN,
    ADS1115_PRESSURE_CHANNEL, ADS1115_SOIL_MOISTURE_CHANNEL
)


@pytest.fixture(scope='function')
def temp_db(monkeypatch):
    """Create a temporary database for testing."""
    # Create temporary directory
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, 'test_irrigation.db')
    
    # Create new engine with test database
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker, scoped_session
    from app.config.database import Base
    
    test_engine = create_engine(f'sqlite:///{db_path}', connect_args={'check_same_thread': False}, echo=False)
    TestSessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=test_engine))
    
    # Initialize database tables
    from app.models import (
        SensorLog, OperationalLog, SystemLog,
        IrrigationSchedule, FertigationSchedule,
        ZoneConfig, SystemConfig
    )
    Base.metadata.create_all(bind=test_engine)
    
    # Create a custom get_db that uses test database
    def test_get_db():
        """Get test database session."""
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()
    
    yield test_get_db
    
    # Cleanup
    TestSessionLocal.remove()
    test_engine.dispose()
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def mock_gpio():
    """Create a mock GPIO instance."""
    return MockGPIO()


@pytest.fixture
def mock_adc():
    """Create a mock ADC instance with controllable values."""
    adc = ADS1115ADC(i2c_address=0x48, use_mock=True)
    # Initialize with default values
    adc.set_mock_value(ADS1115_SOIL_MOISTURE_CHANNEL, 0.6)  # ~50% moisture
    adc.set_mock_value(ADS1115_PRESSURE_CHANNEL, 0.5)  # ~250 kPa
    return adc


@pytest.fixture
def mock_soil_moisture_sensors(mock_adc):
    """Create mock soil moisture sensors."""
    sensors = {
        1: SoilMoistureSensor(
            'soil_moisture_1', mock_adc, ADS1115_SOIL_MOISTURE_CHANNEL,
            zone_id=1, dry_value=0.833, wet_value=0.344
        ),
        2: SoilMoistureSensor(
            'soil_moisture_2', mock_adc, 2, zone_id=2,
            dry_value=0.833, wet_value=0.344
        )
    }
    return sensors


@pytest.fixture
def mock_pressure_sensors(mock_adc):
    """Create mock pressure sensors."""
    sensors = {
        1: PressureSensor('pressure_1', mock_adc, ADS1115_PRESSURE_CHANNEL, zone_id=1),
        2: PressureSensor('pressure_2', mock_adc, 3, zone_id=2)
    }
    return sensors


@pytest.fixture
def mock_tank_level_sensor(mock_gpio):
    """Create a mock tank level sensor."""
    sensor = TankLevelSensor(
        'tank_level_1', mock_gpio,
        DEFAULT_TANK_LEVEL_TRIGGER_PIN, DEFAULT_TANK_LEVEL_ECHO_PIN,
        tank_height_cm=50.0
    )
    return sensor


@pytest.fixture
def mock_weather_reader(monkeypatch, tmp_path):
    """Create a mock weather reader with controllable weather."""
    # Create a temporary weather database
    weather_db = tmp_path / 'test_weather.db'
    
    # Set environment variable
    monkeypatch.setenv('WEATHER_DB_PATH', str(weather_db))
    monkeypatch.setattr('app.config.config.WEATHER_DB_PATH', str(weather_db))
    
    # Create database with test data
    import sqlite3
    conn = sqlite3.connect(str(weather_db))
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS weather (
            timestamp TEXT,
            condition TEXT,
            temperature REAL,
            humidity REAL,
            precipitation REAL
        )
    ''')
    # Insert clear weather by default
    cursor.execute('''
        INSERT INTO weather (timestamp, condition, temperature, humidity, precipitation)
        VALUES (?, ?, ?, ?, ?)
    ''', ('2024-01-01 12:00:00', 'clear', 25.0, 50.0, 0.0))
    conn.commit()
    conn.close()
    
    return WeatherReader()


@pytest.fixture
def irrigation_controller(mock_gpio, mock_adc, mock_soil_moisture_sensors,
                         mock_pressure_sensors, mock_weather_reader, temp_db):
    """Create an irrigation controller with mocked dependencies."""
    # Initialize hardware
    pump_controller_hw = SimplePumpController(mock_gpio, PUMP_GPIO_PIN, pressure_sensor_pin=None)
    zone_pins = {1: 17, 2: 18}
    valve_controller_hw = SolenoidValveController(mock_gpio, zone_pins)
    
    # Initialize hydraulic components
    pressure_calculator = PressureCalculator(reference_altitude_m=0.0)
    valve_controller = HydraulicValveController(valve_controller_hw)
    pump_controller = HydraulicPumpController(pump_controller_hw)
    decision_engine = HybridEngine()
    
    # Create controller
    controller = IrrigationController(
        pressure_calculator=pressure_calculator,
        valve_controller=valve_controller,
        pump_controller=pump_controller,
        decision_engine=decision_engine,
        soil_moisture_sensors=mock_soil_moisture_sensors,
        weather_reader=mock_weather_reader,
        pressure_sensors=mock_pressure_sensors,
        db_session_factory=temp_db
    )
    
    return controller


@pytest.fixture
def fertigation_controller(mock_gpio, mock_tank_level_sensor, temp_db):
    """Create a fertigation controller with mocked dependencies."""
    # Initialize hardware
    zone_pins = {1: 17, 2: 18}
    valve_controller_hw = SolenoidValveController(mock_gpio, zone_pins)
    tank_valve_controller = TankValveController(
        mock_gpio, TANK_INLET_SOLENOID_PIN, TANK_OUTLET_SOLENOID_PIN
    )
    
    # Initialize hydraulic components
    valve_controller = HydraulicValveController(valve_controller_hw)
    
    # Create controller
    controller = FertigationController(
        valve_controller=valve_controller,
        tank_valve_controller=tank_valve_controller,
        tank_level_sensor=mock_tank_level_sensor,
        db_session_factory=temp_db
    )
    
    return controller


@pytest.fixture
def app(irrigation_controller, fertigation_controller):
    """Create Flask app for testing."""
    # Set controllers in API modules
    from app.api import irrigation, fertigation
    irrigation.controllers = {
        'irrigation': irrigation_controller,
        'zone_configs': {
            1: {'altitude': 0.0, 'slope': 0.0, 'base_pressure': 200.0},
            2: {'altitude': 0.0, 'slope': 0.0, 'base_pressure': 200.0}
        }
    }
    fertigation.controllers = {
        'fertigation': fertigation_controller
    }
    
    # Create a minimal Flask app for testing
    from flask import Flask
    from flask_cors import CORS
    from app.api import api_bp
    
    flask_app = Flask(__name__)
    CORS(flask_app)
    flask_app.config['TESTING'] = True
    flask_app.register_blueprint(api_bp)
    
    return flask_app


@pytest.fixture
def client(app):
    """Create Flask test client."""
    return app.test_client()

