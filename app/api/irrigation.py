"""Irrigation API endpoints."""
from flask import Blueprint, jsonify, request
from app.api import api_bp
from app.config.config import ZONE_ID
from app.config.database import get_db
from app.utils.system_config_helper import load_system_config

irrigation_bp = Blueprint('irrigation', __name__)
api_bp.register_blueprint(irrigation_bp, url_prefix='/irrigation')

# Global controllers (will be initialized in app.py)
controllers = {}


@irrigation_bp.route('/start', methods=['POST'])
def start_irrigation():
    """Start irrigation for the system zone."""
    try:
        data = request.get_json() or {}
        if not isinstance(data, dict):
            return jsonify({
                'success': False,
                'error': 'Invalid JSON payload',
                'message': 'Request body must be a JSON object'
            }), 400

        irrigation_ctrl = controllers.get('irrigation')
        if not irrigation_ctrl:
            return jsonify({
                'success': False,
                'error': 'Irrigation controller not initialized'
            }), 500

        # Validate requested zone (single-zone system)
        if 'zone_id' not in data:
            return jsonify({
                'success': False,
                'error': 'Missing required field: zone_id'
            }), 400

        requested_zone_id = data.get('zone_id')
        if requested_zone_id != ZONE_ID:
            return jsonify({
                'success': False,
                'error': f'Invalid zone_id {requested_zone_id}; only zone_id={ZONE_ID} is supported'
            }), 404
        
        # Load hydraulic / zone config from database-backed SystemConfig
        db = next(get_db())
        try:
            cfg = load_system_config(db)
        finally:
            db.close()

        zone_config = {
            'slope': cfg.get('zone_slope_degrees'),
            'base_pressure': cfg.get('zone_base_pressure_kpa'),
        }
        
        result = irrigation_ctrl.start_irrigation(ZONE_ID, zone_config)
        
        if result['success']:
            return jsonify(result), 200
        else:
            # Return the actual error message from the result
            return jsonify(result), 400
            
    except TypeError as e:
        # Handle JSON serialization errors specifically
        if 'not JSON serializable' in str(e):
            return jsonify({
                'success': False,
                'error': 'Internal error: Data serialization failed',
                'message': 'An error occurred while processing the irrigation request. Please try again.'
            }), 500
        raise
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'message': str(e)
        }), 500


@irrigation_bp.route('/stop', methods=['POST'])
def stop_irrigation():
    """Stop current irrigation."""
    try:
        irrigation_ctrl = controllers.get('irrigation')
        if not irrigation_ctrl:
            return jsonify({
                'success': False,
                'error': 'Irrigation controller not initialized'
            }), 500
        
        result = irrigation_ctrl.stop_irrigation()
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@irrigation_bp.route('/status', methods=['GET'])
def get_irrigation_status():
    """Get irrigation status."""
    try:
        irrigation_ctrl = controllers.get('irrigation')
        if not irrigation_ctrl:
            return jsonify({
                'success': False,
                'error': 'Irrigation controller not initialized'
            }), 500
        
        status = irrigation_ctrl.get_status()
        return jsonify({
            'success': True,
            'status': status
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

