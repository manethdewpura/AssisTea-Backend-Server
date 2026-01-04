"""Sensor data API endpoints."""
from flask import Blueprint, jsonify
from app.api import api_bp
from datetime import datetime

sensors_bp = Blueprint('sensors', __name__)
api_bp.register_blueprint(sensors_bp, url_prefix='/sensors')

# Global sensors dictionary (will be initialized in main.py)
sensors_dict = {}


@sensors_bp.route('/current', methods=['GET'])
def get_current_sensor_readings():
    """Get current readings from all sensors."""
    try:
        readings = []
        
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
                # If sensor read fails, include error info
                readings.append({
                    'sensor_id': sensor_key,
                    'sensor_type': sensor_key,
                    'zone_id': getattr(sensor, 'zone_id', None),
                    'error': str(e),
                    'is_healthy': False,
                    'timestamp': datetime.now().isoformat()
                })
        
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

