"""Irrigation API endpoints."""
from flask import Blueprint, jsonify, request
from app.api import api_bp
from app.config.config import (
    ZONE_ID, ZONE_ALTITUDE_M, ZONE_SLOPE_DEGREES, ZONE_BASE_PRESSURE_KPA
)

irrigation_bp = Blueprint('irrigation', __name__)
api_bp.register_blueprint(irrigation_bp, url_prefix='/irrigation')

# Global controllers (will be initialized in app.py)
controllers = {}


@irrigation_bp.route('/start', methods=['POST'])
def start_irrigation():
    """Start irrigation for the system zone."""
    try:
        irrigation_ctrl = controllers.get('irrigation')
        if not irrigation_ctrl:
            return jsonify({
                'success': False,
                'error': 'Irrigation controller not initialized'
            }), 500
        
        # Build zone_config dictionary from hardcoded config values
        zone_config = {
            'altitude': ZONE_ALTITUDE_M,
            'slope': ZONE_SLOPE_DEGREES,
            'base_pressure': ZONE_BASE_PRESSURE_KPA
        }
        
        result = irrigation_ctrl.start_irrigation(ZONE_ID, zone_config)
        
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
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

