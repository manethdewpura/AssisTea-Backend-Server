"""System control and configuration API endpoints."""
from flask import Blueprint, jsonify, request
from app.api import api_bp
from app.config.config import (
    ZONE_ID,
    ZONE_VALVE_GPIO_PIN,
    ZONE_SOIL_MOISTURE_SENSOR_CHANNEL,
)
from app.config.database import get_db
from app.utils.system_config_helper import load_system_config, update_system_config

system_bp = Blueprint('system', __name__)
api_bp.register_blueprint(system_bp, url_prefix='/system')

# Global system state (will be initialized in app.py)
system_state = {
    'is_running': False,
    'controllers': None
}


@system_bp.route('/start', methods=['POST'])
def start_system():
    """Start the irrigation system."""
    try:
        system_state['is_running'] = True
        return jsonify({
            'success': True,
            'message': 'System started',
            'status': 'running'
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@system_bp.route('/stop', methods=['POST'])
def stop_system():
    """Stop the irrigation system."""
    try:
        system_state['is_running'] = False
        
        # Stop any running operations
        if system_state['controllers']:
            irrigation_ctrl = system_state['controllers'].get('irrigation')
            fertigation_ctrl = system_state['controllers'].get('fertigation')
            
            if irrigation_ctrl and irrigation_ctrl.is_running:
                irrigation_ctrl.stop_irrigation()
            
            if fertigation_ctrl and fertigation_ctrl.is_running:
                fertigation_ctrl.stop_fertigation()
        
        return jsonify({
            'success': True,
            'message': 'System stopped',
            'status': 'stopped'
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@system_bp.route('/status', methods=['GET'])
def get_system_status():
    """Get system status."""
    try:
        status = {
            'is_running': system_state['is_running'],
            'irrigation': None,
            'fertigation': None
        }
        
        if system_state['controllers']:
            irrigation_ctrl = system_state['controllers'].get('irrigation')
            fertigation_ctrl = system_state['controllers'].get('fertigation')
            
            if irrigation_ctrl:
                status['irrigation'] = irrigation_ctrl.get_status()
            
            if fertigation_ctrl:
                status['fertigation'] = fertigation_ctrl.get_status()
        
        return jsonify({
            'success': True,
            'status': status
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@system_bp.route('/zone-info', methods=['GET'])
def get_zone_info():
    """Get zone configuration information (read-only)."""
    try:
        db = next(get_db())
        try:
            cfg = load_system_config(db)
        finally:
            db.close()

        zone_info = {
            'zone_id': ZONE_ID,
            'valve_gpio_pin': ZONE_VALVE_GPIO_PIN,
            'soil_moisture_sensor_channel': ZONE_SOIL_MOISTURE_SENSOR_CHANNEL,
            'slope': cfg.get('zone_slope_degrees'),
            'area': cfg.get('zone_area_m2'),
            'base_pressure': cfg.get('zone_base_pressure_kpa'),
        }
        
        return jsonify({
            'success': True,
            'zone': zone_info
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@system_bp.route('/config', methods=['GET'])
def get_system_config():
    """Get system-wide hydraulic and zone configuration (single-zone system)."""
    try:
        db = next(get_db())
        try:
            cfg = load_system_config(db)
        finally:
            db.close()

        return jsonify({
            'success': True,
            'config': cfg
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@system_bp.route('/config', methods=['PUT', 'PATCH'])
def update_system_config_route():
    """
    Update system-wide hydraulic and zone configuration.

    Accepts a JSON body with any subset of:
      - zone_slope_degrees
      - zone_area_m2
      - zone_base_pressure_kpa
      - pipe_length_m
      - pipe_diameter_m
      - estimated_flow_rate_m3_per_s
    """
    try:
        data = request.get_json() or {}
        if not isinstance(data, dict):
            return jsonify({
                'success': False,
                'error': 'Invalid JSON payload'
            }), 400

        db = next(get_db())
        try:
            update_result = update_system_config(db, data)
        finally:
            db.close()

        cfg = update_result.get('config', {})
        applied_keys = update_result.get('applied_keys', [])
        unknown_keys = update_result.get('unknown_keys', [])
        invalid_values = update_result.get('invalid_values', {})

        # If nothing was successfully applied, treat this as a bad request so
        # clients can detect rejected updates.
        if not applied_keys:
            return jsonify({
                'success': False,
                'error': 'No configuration values were updated',
                'details': {
                    'unknown_keys': unknown_keys,
                    'invalid_values': invalid_values,
                },
            }), 400

        response_body = {
            'success': True,
            'config': cfg,
            'applied_keys': applied_keys,
        }

        # Surface partial failures as warnings while still returning success.
        if unknown_keys or invalid_values:
            response_body['warnings'] = {
                'unknown_keys': unknown_keys,
                'invalid_values': invalid_values,
            }

        return jsonify(response_body), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

