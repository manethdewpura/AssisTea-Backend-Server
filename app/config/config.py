"""System configuration settings."""
import os

# Environment detection
IS_RASPBERRY_PI = os.path.exists('/proc/device-tree/model') or os.getenv('USE_REAL_GPIO', 'false').lower() == 'true'
USE_MOCK_HARDWARE = not IS_RASPBERRY_PI or os.getenv('USE_MOCK_HARDWARE', 'false').lower() == 'true'

# GPIO Pin Configuration
# Pump control
PUMP_GPIO_PIN = int(os.getenv('PUMP_GPIO_PIN', '18'))

# Fertilizer tank solenoids
TANK_INLET_SOLENOID_PIN = int(os.getenv('TANK_INLET_SOLENOID_PIN', '23'))
TANK_OUTLET_SOLENOID_PIN = int(os.getenv('TANK_OUTLET_SOLENOID_PIN', '24'))

# ADS1115 ADC Configuration (for soil moisture and pressure sensors)
ADS1115_I2C_ADDRESS = int(os.getenv('ADS1115_I2C_ADDRESS', '0x48'), 16)  # Default I2C address
ADS1115_PRESSURE_CHANNEL = int(os.getenv('ADS1115_PRESSURE_CHANNEL', '0'))  # Channel 0 for pressure
ADS1115_SOIL_MOISTURE_CHANNEL = int(os.getenv('ADS1115_SOIL_MOISTURE_CHANNEL', '1'))  # Channel 1 for soil moisture

# Sensor pins (for digital sensors and tank level)
DEFAULT_TANK_LEVEL_TRIGGER_PIN = int(os.getenv('DEFAULT_TANK_LEVEL_TRIGGER_PIN', '27'))
DEFAULT_TANK_LEVEL_ECHO_PIN = int(os.getenv('DEFAULT_TANK_LEVEL_ECHO_PIN', '28'))

# System thresholds
MIN_SOIL_MOISTURE_PERCENT = float(os.getenv('MIN_SOIL_MOISTURE_PERCENT', '0.0'))  # 0% = completely dry (valid)
MAX_SOIL_MOISTURE_PERCENT = float(os.getenv('MAX_SOIL_MOISTURE_PERCENT', '100.0'))  # 100% = completely saturated (valid)
ADEQUATE_SOIL_MOISTURE_PERCENT = float(os.getenv('ADEQUATE_SOIL_MOISTURE_PERCENT', '60.0'))

MIN_PRESSURE_KPA = float(os.getenv('MIN_PRESSURE_KPA', '100.0'))
MAX_PRESSURE_KPA = float(os.getenv('MAX_PRESSURE_KPA', '500.0'))

TANK_EMPTY_LEVEL_CM = float(os.getenv('TANK_EMPTY_LEVEL_CM', '5.0'))
TANK_FULL_LEVEL_CM = float(os.getenv('TANK_FULL_LEVEL_CM', '50.0'))

# Hydraulic constants
WATER_DENSITY_KG_PER_M3 = 1000.0
GRAVITY_M_PER_S2 = 9.81
PRESSURE_LOSS_PER_DEGREE_SLOPE_KPA = float(os.getenv('PRESSURE_LOSS_PER_DEGREE_SLOPE_KPA', '2.5'))

# Pump control
PUMP_PRESSURE_TOLERANCE_KPA = float(os.getenv('PUMP_PRESSURE_TOLERANCE_KPA', '10.0'))
PUMP_ADJUSTMENT_INTERVAL_SEC = float(os.getenv('PUMP_ADJUSTMENT_INTERVAL_SEC', '2.0'))

# Sensor reading intervals
SENSOR_READ_INTERVAL_SEC = float(os.getenv('SENSOR_READ_INTERVAL_SEC', '5.0'))
MOISTURE_CHECK_INTERVAL_SEC = float(os.getenv('MOISTURE_CHECK_INTERVAL_SEC', '10.0'))

# Safety settings
MAX_OPERATION_DURATION_SEC = float(os.getenv('MAX_OPERATION_DURATION_SEC', '3600.0'))  # 1 hour max
SENSOR_FAILURE_THRESHOLD = int(os.getenv('SENSOR_FAILURE_THRESHOLD', '3'))  # Consecutive failures
ABNORMAL_READING_THRESHOLD = float(os.getenv('ABNORMAL_READING_THRESHOLD', '3.0'))  # Standard deviations

# Weather database path (existing SQLite database)
WEATHER_DB_PATH = os.getenv('WEATHER_DB_PATH', os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'database', 'weather.db'))

