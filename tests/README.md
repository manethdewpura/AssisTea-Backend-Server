# Test Suite for Irrigation and Fertigation System

This directory contains comprehensive tests for the irrigation and fertigation backend system.

## Test Structure

- `conftest.py` - Shared pytest fixtures for test setup
- `test_irrigation.py` - Tests for irrigation API and controller
- `test_fertigation.py` - Tests for fertigation API and controller
- `run_tests.py` - Script to run all tests

## Running Tests

### Install Dependencies

First, install the test dependencies:

```bash
pip install -r requirements.txt
```

### Run All Tests

```bash
# Using pytest directly
pytest tests/ -v

# Or using the test runner script
python tests/run_tests.py
```

### Run Specific Test Files

```bash
# Run only irrigation tests
pytest tests/test_irrigation.py -v

# Run only fertigation tests
pytest tests/test_fertigation.py -v
```

### Run Specific Test Classes or Methods

```bash
# Run a specific test class
pytest tests/test_irrigation.py::TestIrrigationAPI -v

# Run a specific test method
pytest tests/test_irrigation.py::TestIrrigationAPI::test_start_irrigation_success -v
```

## Test Coverage

### Irrigation Tests

- **API Tests**: Test all irrigation API endpoints (start, stop, status)
- **Controller Tests**: Test irrigation controller logic
- **Sensor Simulation**: Test different soil moisture and pressure scenarios
- **Weather Checks**: Test irrigation blocking due to bad weather
- **Edge Cases**: Test invalid inputs, already running operations, etc.

### Fertigation Tests

- **API Tests**: Test all fertigation API endpoints (start, stop, status)
- **Controller Tests**: Test fertigation controller logic
- **Tank Level Monitoring**: Test tank level sensor integration
- **Edge Cases**: Test invalid inputs, already running operations, etc.

### Sensor Simulation Tests

- **Soil Moisture**: Simulate different moisture levels (dry, wet, adequate)
- **Pressure**: Simulate different pressure readings
- **Tank Level**: Test tank level sensor readings

### Fail-Safe Tests (`test_fail_safes.py`)

- **Sensor Failure Handler**: Test sensor failure detection and recovery
- **Abnormal Reading Handler**: Test detection of abnormal sensor readings
- **Emergency Stop**: Test emergency stop mechanism
- **Health Monitor**: Test system health monitoring
- **Integration Tests**: Test fail-safes with controllers
- **Failure Scenarios**: Test scenarios where operations should be prevented

## Simulating Sensor Inputs

The tests use mock sensors that can be controlled programmatically:

### Soil Moisture Simulation

```python
# Set soil moisture to 30% (low, needs irrigation)
# For dry_value=0.833, wet_value=0.344:
# normalized = 0.833 - (0.3 * (0.833 - 0.344)) = 0.686
mock_adc.set_mock_value(1, 0.686)  # Channel 1 for soil moisture

# Set soil moisture to 70% (high, adequate)
# normalized = 0.833 - (0.7 * (0.833 - 0.344)) = 0.491
mock_adc.set_mock_value(1, 0.491)
```

### Pressure Simulation

```python
# Set pressure to 100 kPa (low)
# normalized = 100 / 500 = 0.2
mock_adc.set_mock_value(0, 0.2)  # Channel 0 for pressure

# Set pressure to 400 kPa (high)
# normalized = 400 / 500 = 0.8
mock_adc.set_mock_value(0, 0.8)
```

## Test Fixtures

The test suite uses several fixtures defined in `conftest.py`:

- `temp_db` - Temporary database for each test
- `mock_gpio` - Mock GPIO interface
- `mock_adc` - Mock ADC with controllable values
- `mock_soil_moisture_sensors` - Mock soil moisture sensors
- `mock_pressure_sensors` - Mock pressure sensors
- `mock_tank_level_sensor` - Mock tank level sensor
- `mock_weather_reader` - Mock weather reader
- `irrigation_controller` - Irrigation controller with mocked dependencies
- `fertigation_controller` - Fertigation controller with mocked dependencies
- `app` - Flask test application
- `client` - Flask test client

## Notes

- All tests use mock hardware, so they can run without physical hardware
- Each test uses a temporary database that is cleaned up after the test
- Sensor values can be controlled programmatically for testing different scenarios
- Tests are designed to be fast and isolated from each other

