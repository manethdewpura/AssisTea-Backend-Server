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
    IRRIGATION_PUMP_GPIO_PIN, FERTILIZER_PUMP_GPIO_PIN, IRRIGATION_PUMP_SOLENOID_PIN,
    TANK_INLET_SOLENOID_PIN, TANK_OUTLET_SOLENOID_PIN,
    DEFAULT_TANK_LEVEL_TRIGGER_PIN, DEFAULT_TANK_LEVEL_ECHO_PIN
)

# Initialize ML background task (checks for stale data every 30 minutes)
# This will automatically generate ML predictions when data is stale
try:
    init_background_task(app, check_interval_seconds=1800)  # 30 minutes
    logging.info("✓ ML background task initialized")
except Exception as e:
    logging.warning(f"ML background task not available: {e}")

# Initialize solenoid state manager for persistent storage
from app.services.solenoid_state_manager import SolenoidStateManager
solenoid_state_manager = SolenoidStateManager()
logging.info("✓ Solenoid state manager initialized")

# Initialize pumps (separate irrigation and fertilizer pumps)
# Note: Pressure reading is done via PressureSensor using ADS1115, not GPIO pin
irrigation_pump_controller_hw = SimplePumpController(gpio, IRRIGATION_PUMP_GPIO_PIN, pressure_sensor_pin=None)
fertilizer_pump_controller_hw = SimplePumpController(gpio, FERTILIZER_PUMP_GPIO_PIN, pressure_sensor_pin=None)

# Initialize irrigation pump solenoid valve with state manager
from app.hardware.irrigation_pump_solenoid import IrrigationPumpSolenoid
irrigation_pump_solenoid = IrrigationPumpSolenoid(gpio, IRRIGATION_PUMP_SOLENOID_PIN, solenoid_state_manager)
logging.info("✓ Irrigation pump solenoid initialized with state persistence")

# Initialize tank valves with state manager
tank_valve_controller = TankValveController(
    gpio, TANK_INLET_SOLENOID_PIN, TANK_OUTLET_SOLENOID_PIN, solenoid_state_manager
)
logging.info("✓ Tank valve controller initialized with state persistence")

# Initialize ADS1115 ADC for analog sensors (soil moisture and pressure)
from app.hardware.ads1115_adc import ADS1115ADC
from app.config.config import (
    ADS1115_I2C_ADDRESS, ADS1115_PRESSURE_CHANNEL, 
    ADS1115_FERTILIZER_PRESSURE_CHANNEL
)

# Create ADC instance (uses I2C on SDA/SCL pins)
adc = ADS1115ADC(i2c_address=ADS1115_I2C_ADDRESS, use_mock=USE_MOCK_HARDWARE)

# Initialize sensors
from app.sensors.pressure import PressureSensor
from app.sensors.soil_moisture import SoilMoistureSensor
from app.sensors.tank_level import TankLevelSensor
from app.sensors.weather import WeatherReader
from app.config.config import (
    ZONE_ID, ZONE_VALVE_GPIO_PIN, ZONE_SOIL_MOISTURE_SENSOR_CHANNEL
)

# Initialize single zone with hardcoded configuration
# Calibration values based on actual sensor readings:
# Dry (out of water): 2.750V = 0.833 normalized (0% moisture)
# Wet (in water): 1.136V = 0.344 normalized (100% moisture)
logging.info(f"Initializing single zone (zone_id={ZONE_ID}) with hardcoded configuration")

# Initialize soil moisture sensor for the single zone
soil_moisture_sensors = {}
zone_pins = {ZONE_ID: ZONE_VALVE_GPIO_PIN}

# Create soil moisture sensor with hardcoded channel
soil_moisture_sensors[ZONE_ID] = SoilMoistureSensor(
    f'soil_moisture_{ZONE_ID}', 
    adc, 
    ZONE_SOIL_MOISTURE_SENSOR_CHANNEL, 
    zone_id=ZONE_ID,
    dry_value=0.833, 
    wet_value=0.344
)
logging.info(f"✓ Soil moisture sensor initialized for zone {ZONE_ID} on ADS1115 channel {ZONE_SOIL_MOISTURE_SENSOR_CHANNEL}")
logging.info(f"✓ Zone valve GPIO pin: {ZONE_VALVE_GPIO_PIN}")

# Irrigation pump pressure sensor on A2 (channel 2) - system-wide (common for all zones)
irrigation_pressure_sensor = PressureSensor('pressure_irrigation', adc, ADS1115_PRESSURE_CHANNEL, zone_id=None)  # A2 for irrigation pump
logging.info("✓ Irrigation pressure sensor initialized (system-wide)")

# Fertilizer pump pressure sensor on A3 (channel 3) - system-wide
fertilizer_pressure_sensor = PressureSensor('pressure_fertilizer', adc, ADS1115_FERTILIZER_PRESSURE_CHANNEL, zone_id=None)  # A3 for fertilizer pump
logging.info("✓ Fertilizer pressure sensor initialized (system-wide)")
tank_level_sensor = TankLevelSensor(
    'tank_level_1', gpio, DEFAULT_TANK_LEVEL_TRIGGER_PIN, DEFAULT_TANK_LEVEL_ECHO_PIN
)
weather_reader = WeatherReader(app=app)

# Initialize zone valve controller with hardcoded zone pin
valve_controller_hw = SolenoidValveController(gpio, zone_pins)
logging.info(f"✓ Zone valve controller initialized with zone {ZONE_ID} (GPIO pin {ZONE_VALVE_GPIO_PIN})")

# Initialize hydraulic components
from app.hydraulics.pressure_calculator import PressureCalculator
from app.hydraulics.valve_controller import HydraulicValveController
from app.hydraulics.pump_controller import HydraulicPumpController

pressure_calculator = PressureCalculator(reference_altitude_m=0.0)
valve_controller = HydraulicValveController(valve_controller_hw)
irrigation_pump_controller = HydraulicPumpController(irrigation_pump_controller_hw)
fertilizer_pump_controller = HydraulicPumpController(fertilizer_pump_controller_hw)

# Initialize decision engine
from app.decision_engine.hybrid_engine import HybridEngine
decision_engine = HybridEngine()

# Initialize cycle controllers
from app.controllers.irrigation_controller import IrrigationController
from app.controllers.fertigation_controller import FertigationController

irrigation_controller = IrrigationController(
    pressure_calculator=pressure_calculator,
    valve_controller=valve_controller,
    pump_controller=irrigation_pump_controller,
    decision_engine=decision_engine,
    soil_moisture_sensors=soil_moisture_sensors,
    weather_reader=weather_reader,
    pressure_sensor=irrigation_pressure_sensor,
    db_session_factory=get_db
)

# Initialize fertigation controller with separate irrigation and fertilizer pumps
fertigation_controller = FertigationController(
    valve_controller=valve_controller,
    tank_valve_controller=tank_valve_controller,
    tank_level_sensor=tank_level_sensor,
    db_session_factory=get_db,
    weather_reader=weather_reader,
    check_weather=False,  # Weather checking disabled per specification
    pressure_sensor=fertilizer_pressure_sensor,  # A3 pressure sensor for fertilizer pump
    fertilizer_pump_controller=fertilizer_pump_controller,  # Fertilizer pump (GPIO 22)
    irrigation_pump_controller=irrigation_pump_controller,  # Irrigation pump (GPIO 23)
    irrigation_pump_solenoid=irrigation_pump_solenoid  # Irrigation pump solenoid (GPIO 24)
)

# Initialize fail-safe mechanisms
from app.safety.fail_safe import (
    SensorFailureHandler, AbnormalReadingHandler, EmergencyStop, HealthMonitor
)

emergency_stop = EmergencyStop()
sensor_failure_handler = SensorFailureHandler(get_db)
abnormal_reading_handler = AbnormalReadingHandler(get_db)

all_sensors = {}
# Add all soil moisture sensors (dynamically loaded from database)
for zone_id, sensor in soil_moisture_sensors.items():
    all_sensors[f'soil_moisture_{zone_id}'] = sensor
    logging.info(f"✓ Added soil moisture sensor for zone {zone_id} to sensors dict")

# Add irrigation pressure sensor (system-wide, common for all zones)
all_sensors['pressure_irrigation'] = irrigation_pressure_sensor
logging.info("✓ Added irrigation pressure sensor to sensors dict (system-wide)")

# Add fertilizer pressure sensor (system-wide)
all_sensors['pressure_fertilizer'] = fertilizer_pressure_sensor
logging.info("✓ Added fertilizer pressure sensor to sensors dict")

# Add tank level sensor
all_sensors['tank_level'] = tank_level_sensor
logging.info("✓ Added tank level sensor to sensors dict")

logging.info(f"✓ Total sensors registered: {len(all_sensors)}")
logging.info(f"  - Soil moisture sensors: {len(soil_moisture_sensors)}")
logging.info(f"  - Irrigation pressure sensor: 1 (system-wide)")
logging.info(f"  - Fertilizer pressure sensor: 1 (system-wide)")
logging.info(f"  - Tank level sensor: 1")
logging.info(f"  - Available sensor keys: {list(all_sensors.keys())}")

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
from app.api import system, irrigation, fertigation, sensors, solenoids
system.system_state['controllers'] = {
    'irrigation': irrigation_controller,
    'fertigation': fertigation_controller
}
irrigation.controllers = {
    'irrigation': irrigation_controller
}
fertigation.controllers = {
    'fertigation': fertigation_controller
}
# Set up sensors reference for API
sensors.sensors_dict = all_sensors
logging.info(f"✓ Sensors dict set in API module with {len(all_sensors)} sensors: {list(all_sensors.keys())}")

# Set up hardware instances for mock value control (only in mock mode)
if USE_MOCK_HARDWARE:
    sensors.adc_instance = adc
    sensors.gpio_instance = gpio

# Set up solenoid state manager for API
solenoids.state_manager = solenoid_state_manager

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
