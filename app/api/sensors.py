"""Sensor data API endpoints."""
from flask import Blueprint, jsonify, request
from app.api import api_bp
from datetime import datetime
from app.config.config import USE_MOCK_HARDWARE

sensors_bp = Blueprint('sensors', __name__)
api_bp.register_blueprint(sensors_bp, url_prefix='/sensors')

# Global sensors dictionary (will be initialized in main.py)
sensors_dict = {}

# Global hardware instances for mock value control (will be initialized in main.py)
adc_instance = None
gpio_instance = None


@sensors_bp.route('/current', methods=['GET'])
def get_current_sensor_readings():
    """Get current readings from all sensors."""
    try:
        readings = []
        
        # Debug: Log available sensors
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Available sensors in sensors_dict: {list(sensors_dict.keys())}")
        
        # Read from all sensors
        for sensor_key, sensor in sensors_dict.items():
            try:
                # Always read fresh value from sensor for real-time monitoring
                reading = sensor.read_standardized()
                
                # Format reading for API response
                reading_data = {
                    'sensor_id': reading.get('sensor_id', sensor_key),
                    'sensor_type': sensor_key,
                    'zone_id': reading.get('zone_id'),
                    'value': reading.get('value'),
                    'unit': reading.get('unit'),
                    'raw_value': reading.get('raw_value'),
                    'raw_unit': reading.get('raw_unit'),
                    'timestamp': reading.get('timestamp').isoformat() if reading.get('timestamp') else datetime.now().isoformat(),
                    'is_healthy': sensor.is_sensor_healthy()
                }
                
                # Add percentage value if available (for tank level)
                if 'value_percent' in reading:
                    reading_data['value_percent'] = reading.get('value_percent')
                
                readings.append(reading_data)
            except Exception as e:
                # If sensor read fails, include error info but still show the sensor
                logger.warning(f"Failed to read sensor {sensor_key}: {str(e)}")
                readings.append({
                    'sensor_id': sensor_key,
                    'sensor_type': sensor_key,
                    'zone_id': getattr(sensor, 'zone_id', None),
                    'error': str(e),
                    'is_healthy': False,
                    'timestamp': datetime.now().isoformat()
                })
        
        logger.info(f"Returning {len(readings)} sensor readings")
        return jsonify({
            'success': True,
            'readings': readings,
            'count': len(readings),
            'timestamp': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@sensors_bp.route('/current/<sensor_type>', methods=['GET'])
def get_current_sensor_reading(sensor_type):
    """Get current reading from a specific sensor type."""
    try:
        sensor = sensors_dict.get(sensor_type)
        
        if sensor is None:
            return jsonify({
                'success': False,
                'error': f'Sensor type {sensor_type} not found'
            }), 404
        
        try:
            # Always read fresh value from sensor for real-time monitoring
            reading = sensor.read_standardized()
            
            # Format reading for API response
            reading_data = {
                'sensor_id': reading.get('sensor_id', sensor_type),
                'sensor_type': sensor_type,
                'zone_id': reading.get('zone_id'),
                'value': reading.get('value'),
                'unit': reading.get('unit'),
                'raw_value': reading.get('raw_value'),
                'raw_unit': reading.get('raw_unit'),
                'timestamp': reading.get('timestamp').isoformat() if reading.get('timestamp') else datetime.now().isoformat(),
                'is_healthy': sensor.is_sensor_healthy()
            }
            
            # Add percentage value if available (for tank level)
            if 'value_percent' in reading:
                reading_data['value_percent'] = reading.get('value_percent')
            
            return jsonify({
                'success': True,
                'reading': reading_data
            }), 200
            
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'Failed to read sensor {sensor_type}: {str(e)}',
                'is_healthy': False
            }), 500
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@sensors_bp.route('/mock/status', methods=['GET'])
def get_mock_status():
    """Get status of mock hardware system."""
    return jsonify({
        'success': True,
        'mock_hardware_enabled': USE_MOCK_HARDWARE,
        'adc_available': adc_instance is not None,
        'gpio_available': gpio_instance is not None,
        'available_sensors': list(sensors_dict.keys()),
        'note': 'Use /mock/set_sensor_value to set sensor values, or /mock/set_adc_channel and /mock/set_gpio_pin for direct control'
    }), 200


@sensors_bp.route('/mock/set_adc_channel', methods=['POST'])
def set_mock_adc_channel():
    """
    Set mock value for an ADS1115 ADC channel (for testing only).
    Only works when USE_MOCK_HARDWARE is enabled.
    
    Request body:
    {
        "channel": 0-3,
        "value": 0.0-1.0 (normalized value)
    }
    """
    if not USE_MOCK_HARDWARE:
        return jsonify({
            'success': False,
            'error': 'Mock hardware is not enabled. This endpoint only works in mock mode.'
        }), 400
    
    if adc_instance is None:
        return jsonify({
            'success': False,
            'error': 'ADC instance not available'
        }), 500
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'Request body is required'
            }), 400
        
        channel = data.get('channel')
        value = data.get('value')
        
        if channel is None or value is None:
            return jsonify({
                'success': False,
                'error': 'Both "channel" (0-3) and "value" (0.0-1.0) are required'
            }), 400
        
        if not isinstance(channel, int) or channel < 0 or channel > 3:
            return jsonify({
                'success': False,
                'error': 'Channel must be an integer between 0 and 3'
            }), 400
        
        if not isinstance(value, (int, float)) or value < 0.0 or value > 1.0:
            return jsonify({
                'success': False,
                'error': 'Value must be a number between 0.0 and 1.0'
            }), 400
        
        # Set the mock value
        adc_instance.set_mock_value(channel, float(value))
        
        return jsonify({
            'success': True,
            'message': f'Mock value set for ADC channel {channel}',
            'channel': channel,
            'value': float(value)
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@sensors_bp.route('/mock/set_gpio_pin', methods=['POST'])
def set_mock_gpio_pin():
    """
    Set mock analog value for a GPIO pin (for testing only).
    Only works when USE_MOCK_HARDWARE is enabled.
    
    Request body:
    {
        "pin": GPIO pin number,
        "value": 0.0-1.0 (normalized analog value)
    }
    """
    if not USE_MOCK_HARDWARE:
        return jsonify({
            'success': False,
            'error': 'Mock hardware is not enabled. This endpoint only works in mock mode.'
        }), 400
    
    if gpio_instance is None:
        return jsonify({
            'success': False,
            'error': 'GPIO instance not available'
        }), 500
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'Request body is required'
            }), 400
        
        pin = data.get('pin')
        value = data.get('value')
        
        if pin is None or value is None:
            return jsonify({
                'success': False,
                'error': 'Both "pin" and "value" (0.0-1.0) are required'
            }), 400
        
        if not isinstance(pin, int) or pin < 0:
            return jsonify({
                'success': False,
                'error': 'Pin must be a non-negative integer'
            }), 400
        
        if not isinstance(value, (int, float)) or value < 0.0 or value > 1.0:
            return jsonify({
                'success': False,
                'error': 'Value must be a number between 0.0 and 1.0'
            }), 400
        
        # Set the mock value
        gpio_instance.set_analog_value(pin, float(value))
        
        return jsonify({
            'success': True,
            'message': f'Mock value set for GPIO pin {pin}',
            'pin': pin,
            'value': float(value)
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@sensors_bp.route('/mock/set_sensor_value', methods=['POST'])
def set_mock_sensor_value():
    """
    Set mock value for a sensor by sensor type (user-friendly interface).
    Only works when USE_MOCK_HARDWARE is enabled.
    
    Request body examples:
    
    Soil Moisture (percentage):
    {
        "sensor_type": "soil_moisture_1",
        "moisture_percent": 30.0  // 0-100%
    }
    
    Pressure (kPa):
    {
        "sensor_type": "pressure_irrigation",
        "pressure_kpa": 250.0  // kPa
    }
    
    Tank Level (cm):
    {
        "sensor_type": "tank_level",
        "level_cm": 25.0  // cm
    }
    """
    if not USE_MOCK_HARDWARE:
        return jsonify({
            'success': False,
            'error': 'Mock hardware is not enabled. This endpoint only works in mock mode.'
        }), 400
    
    if adc_instance is None or gpio_instance is None:
        return jsonify({
            'success': False,
            'error': 'Hardware instances not available'
        }), 500
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'Request body is required'
            }), 400
        
        sensor_type = data.get('sensor_type')
        if not sensor_type:
            return jsonify({
                'success': False,
                'error': 'sensor_type is required'
            }), 400
        
        sensor = sensors_dict.get(sensor_type)
        if sensor is None:
            return jsonify({
                'success': False,
                'error': f'Sensor type "{sensor_type}" not found'
            }), 404
        
        # Handle different sensor types
        if sensor_type.startswith('soil_moisture'):
            # Soil moisture sensor - expects moisture_percent (0-100%)
            moisture_percent = data.get('moisture_percent')
            if moisture_percent is None:
                return jsonify({
                    'success': False,
                    'error': 'moisture_percent (0-100) is required for soil moisture sensors'
                }), 400
            
            moisture_percent = float(moisture_percent)
            if moisture_percent < 0 or moisture_percent > 100:
                return jsonify({
                    'success': False,
                    'error': 'moisture_percent must be between 0 and 100'
                }), 400
            
            # Convert moisture percentage to normalized value
            # Formula: normalized = dry_value - (moisture_percent/100 * (dry_value - wet_value))
            dry_value = sensor.dry_value
            wet_value = sensor.wet_value
            normalized = dry_value - (moisture_percent / 100.0 * (dry_value - wet_value))
            
            # Set the ADC channel value
            adc_instance.set_mock_value(sensor.channel, normalized)
            
            return jsonify({
                'success': True,
                'message': f'Soil moisture set to {moisture_percent:.1f}%',
                'sensor_type': sensor_type,
                'moisture_percent': moisture_percent,
                'normalized_value': normalized,
                'channel': sensor.channel
            }), 200
        
        elif sensor_type.startswith('pressure'):
            # Pressure sensor - expects pressure_kpa
            pressure_kpa = data.get('pressure_kpa')
            if pressure_kpa is None:
                return jsonify({
                    'success': False,
                    'error': 'pressure_kpa is required for pressure sensors'
                }), 400
            
            pressure_kpa = float(pressure_kpa)
            if pressure_kpa < sensor.min_pressure_kpa or pressure_kpa > sensor.max_pressure_kpa:
                return jsonify({
                    'success': False,
                    'error': f'pressure_kpa must be between {sensor.min_pressure_kpa} and {sensor.max_pressure_kpa} kPa'
                }), 400
            
            # Convert pressure to normalized value
            # Formula: normalized = (pressure - min_pressure) / (max_pressure - min_pressure)
            pressure_range = sensor.max_pressure_kpa - sensor.min_pressure_kpa
            normalized = (pressure_kpa - sensor.min_pressure_kpa) / pressure_range if pressure_range > 0 else 0.5
            
            # Set the ADC channel value
            adc_instance.set_mock_value(sensor.channel, normalized)
            
            return jsonify({
                'success': True,
                'message': f'Pressure set to {pressure_kpa:.1f} kPa',
                'sensor_type': sensor_type,
                'pressure_kpa': pressure_kpa,
                'normalized_value': normalized,
                'channel': sensor.channel
            }), 200
        
        elif sensor_type == 'tank_level':
            # Tank level sensor - expects level_cm
            level_cm = data.get('level_cm')
            if level_cm is None:
                return jsonify({
                    'success': False,
                    'error': 'level_cm is required for tank level sensor'
                }), 400
            
            level_cm = float(level_cm)
            if level_cm < 0 or level_cm > sensor.tank_height_cm:
                return jsonify({
                    'success': False,
                    'error': f'level_cm must be between 0 and {sensor.tank_height_cm} cm'
                }), 400
            
            # Convert level to distance (ultrasonic sensor measures distance, not level)
            # Distance = tank_height - level
            distance_cm = sensor.tank_height_cm - level_cm
            
            # For ultrasonic sensor, we need to simulate the timing
            # Speed of sound = 343 m/s = 0.0343 cm/μs
            # pulse_duration = (distance * 2) / 34300
            # This is complex, so we'll set a GPIO analog value that approximates it
            # For simplicity, we'll use a normalized value based on distance
            # Max distance = tank_height, so normalized = distance / tank_height
            normalized = distance_cm / sensor.tank_height_cm if sensor.tank_height_cm > 0 else 0.5
            
            # Note: Tank level sensor uses GPIO pins, not ADC
            # We'll need to set the analog value on the echo pin
            # This is a simplified approach - in reality, ultrasonic timing is more complex
            gpio_instance.set_analog_value(sensor.echo_pin, normalized)
            
            return jsonify({
                'success': True,
                'message': f'Tank level set to {level_cm:.1f} cm',
                'sensor_type': sensor_type,
                'level_cm': level_cm,
                'level_percent': (level_cm / sensor.tank_height_cm * 100) if sensor.tank_height_cm > 0 else 0,
                'note': 'Tank level simulation is simplified - actual ultrasonic timing is more complex'
            }), 200
        
        else:
            return jsonify({
                'success': False,
                'error': f'Sensor type "{sensor_type}" does not support mock value setting via this endpoint. Use /mock/set_adc_channel or /mock/set_gpio_pin directly.'
            }), 400
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
