"""Main Flask application for irrigation and fertigation control system."""
from flask import Flask, jsonify
from flask_cors import CORS
from app.models.weather_records import db, init_db
from app.ml.background_task import init_background_task
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Initialize Flask app
app = Flask(__name__)

# Enable CORS for all routes
CORS(app)

# Configure Flask-SQLAlchemy for weather database
from app.config.config import WEATHER_DB_PATH, USE_MOCK_HARDWARE
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{WEATHER_DB_PATH}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize weather database with Flask app
db.init_app(app)

# Create weather database tables
with app.app_context():
    db.create_all()
    logging.info("✓ Weather database initialized")

# Import configuration
from app.config.database import init_db, get_db

# Initialize database
init_db()

# Initialize hardware abstraction
if USE_MOCK_HARDWARE:
    from app.hardware.mock_gpio import MockGPIO
    gpio = MockGPIO()
else:
    from app.hardware.real_gpio import RealGPIO
    gpio = RealGPIO()

# Initialize hardware components
from app.hardware.pump_interface import SimplePumpController
from app.hardware.valve_interface import SolenoidValveController
from app.hardware.tank_valve_controller import TankValveController
from app.config.config import (
    PUMP_GPIO_PIN, TANK_INLET_SOLENOID_PIN, TANK_OUTLET_SOLENOID_PIN,
    DEFAULT_TANK_LEVEL_TRIGGER_PIN, DEFAULT_TANK_LEVEL_ECHO_PIN
)

# Initialize ML background task (checks for stale data every 30 minutes)
# This will automatically generate ML predictions when data is stale
try:
    init_background_task(app, check_interval_seconds=1800)  # 30 minutes
    logging.info("✓ ML background task initialized")
except Exception as e:
    logging.warning(f"ML background task not available: {e}")

# Initialize pump and valves
# Note: Pressure reading is done via PressureSensor using ADS1115, not GPIO pin
pump_controller_hw = SimplePumpController(gpio, PUMP_GPIO_PIN, pressure_sensor_pin=None)
tank_valve_controller = TankValveController(
    gpio, TANK_INLET_SOLENOID_PIN, TANK_OUTLET_SOLENOID_PIN
)

# Initialize ADS1115 ADC for analog sensors (soil moisture and pressure)
from app.hardware.ads1115_adc import ADS1115ADC
from app.config.config import ADS1115_I2C_ADDRESS, ADS1115_PRESSURE_CHANNEL, ADS1115_SOIL_MOISTURE_CHANNEL

# Create ADC instance (uses I2C on SDA/SCL pins)
adc = ADS1115ADC(i2c_address=ADS1115_I2C_ADDRESS, use_mock=USE_MOCK_HARDWARE)

# Initialize sensors
from app.sensors.pressure import PressureSensor
from app.sensors.soil_moisture import SoilMoistureSensor
from app.sensors.tank_level import TankLevelSensor
from app.sensors.weather import WeatherReader

# Create sensor instances (example for zone 1, would be loaded from database)
# Soil moisture and pressure sensors use ADS1115 ADC channels
# ADS1115 has 4 channels (0-3), we can use different channels for different sensors
# Calibration values based on actual sensor readings:
# Dry (out of water): 2.750V = 0.833 normalized (0% moisture)
# Wet (in water): 1.136V = 0.344 normalized (100% moisture)
soil_moisture_sensors = {
    1: SoilMoistureSensor('soil_moisture_1', adc, ADS1115_SOIL_MOISTURE_CHANNEL, zone_id=1, 
                          dry_value=0.833, wet_value=0.344),
    2: SoilMoistureSensor('soil_moisture_2', adc, 2, zone_id=2, 
                          dry_value=0.833, wet_value=0.344)  # Channel 2 for zone 2
}
pressure_sensors = {
    1: PressureSensor('pressure_1', adc, ADS1115_PRESSURE_CHANNEL, zone_id=1),
    2: PressureSensor('pressure_2', adc, 3, zone_id=2)  # Channel 3 for zone 2 pressure
}
tank_level_sensor = TankLevelSensor(
    'tank_level_1', gpio, DEFAULT_TANK_LEVEL_TRIGGER_PIN, DEFAULT_TANK_LEVEL_ECHO_PIN
)
weather_reader = WeatherReader(app=app)

# Initialize zone valve controller (example zone pins, would come from database)
zone_pins = {1: 17}  # Example: zone 1 uses GPIO pin 17
valve_controller_hw = SolenoidValveController(gpio, zone_pins)

# Initialize hydraulic components
from app.hydraulics.pressure_calculator import PressureCalculator
from app.hydraulics.valve_controller import HydraulicValveController
from app.hydraulics.pump_controller import HydraulicPumpController

pressure_calculator = PressureCalculator(reference_altitude_m=0.0)
valve_controller = HydraulicValveController(valve_controller_hw)
pump_controller = HydraulicPumpController(pump_controller_hw)

# Initialize decision engine
from app.decision_engine.hybrid_engine import HybridEngine
decision_engine = HybridEngine()

# Initialize cycle controllers
from app.controllers.irrigation_controller import IrrigationController
from app.controllers.fertigation_controller import FertigationController

irrigation_controller = IrrigationController(
    pressure_calculator=pressure_calculator,
    valve_controller=valve_controller,
    pump_controller=pump_controller,
    decision_engine=decision_engine,
    soil_moisture_sensors=soil_moisture_sensors,
    weather_reader=weather_reader,
    pressure_sensors=pressure_sensors,
    db_session_factory=get_db
)

fertigation_controller = FertigationController(
    valve_controller=valve_controller,
    tank_valve_controller=tank_valve_controller,
    tank_level_sensor=tank_level_sensor,
    db_session_factory=get_db,
    weather_reader=weather_reader,
    check_weather=True  # Enable weather checking for fertigation
)

# Initialize fail-safe mechanisms
from app.safety.fail_safe import (
    SensorFailureHandler, AbnormalReadingHandler, EmergencyStop, HealthMonitor
)

emergency_stop = EmergencyStop()
sensor_failure_handler = SensorFailureHandler(get_db)
abnormal_reading_handler = AbnormalReadingHandler(get_db)

all_sensors = {}
# Add sensors with proper type names as keys
for zone_id, sensor in soil_moisture_sensors.items():
    all_sensors[f'soil_moisture_{zone_id}'] = sensor
for zone_id, sensor in pressure_sensors.items():
    all_sensors[f'pressure_{zone_id}'] = sensor
all_sensors['tank_level'] = tank_level_sensor
# Note: weather sensor is excluded from all_sensors as it's not needed in the mobile app
# all_sensors['weather'] = weather_reader

health_monitor = HealthMonitor(all_sensors, emergency_stop, get_db)

# Initialize scheduler
from app.scheduler.task_scheduler import TaskScheduler

def irrigation_callback(zone_id, zone_config):
    """Callback for scheduled irrigation."""
    if not emergency_stop.is_stopped():
        irrigation_controller.start_irrigation(zone_id, zone_config)

def fertigation_callback(zone_id):
    """Callback for scheduled fertigation."""
    if not emergency_stop.is_stopped():
        fertigation_controller.start_fertigation(zone_id)

task_scheduler = TaskScheduler(irrigation_callback, fertigation_callback)
task_scheduler.start()

# Register API blueprints
from app.api import api_bp
app.register_blueprint(api_bp)

# Set up API controller references
from app.api import system, irrigation, fertigation, sensors
system.system_state['controllers'] = {
    'irrigation': irrigation_controller,
    'fertigation': fertigation_controller
}
irrigation.controllers = {
    'irrigation': irrigation_controller,
    'zone_configs': {1: {'altitude': 0.0, 'slope': 0.0, 'base_pressure': 200.0}}  # Example config
}
fertigation.controllers = {
    'fertigation': fertigation_controller
}
# Set up sensors reference for API
sensors.sensors_dict = all_sensors

# Root route
@app.route('/')
def home():
    """Root endpoint."""
    return jsonify({
        "message": "Irrigation and Fertigation Control System",
        "status": "running",
        "hardware_mode": "mock" if USE_MOCK_HARDWARE else "real"
    })

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    try:
        health_status = health_monitor.check_system_health()
        return jsonify(health_status), 200
    except Exception as e:
        # Return a basic health status even if health check fails
        # This ensures the endpoint is always available for connection testing
        import traceback
        print(f"Health check error: {e}")
        print(traceback.format_exc())
        return jsonify({
            'overall_status': 'error',
            'message': 'Health check encountered an error',
            'error': str(e),
            'server_running': True,
            'timestamp': datetime.now().isoformat()
        }), 200  # Still return 200 so connection test passes

if __name__ == '__main__':
    print("Starting Irrigation and Fertigation Control System...")
    print(f"Hardware mode: {'MOCK' if USE_MOCK_HARDWARE else 'REAL'}")
    app.run(host='0.0.0.0', port=5000, debug=True)
