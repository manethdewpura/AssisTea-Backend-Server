"""Irrigation API endpoints."""
from flask import Blueprint, jsonify, request
from app.api import api_bp

irrigation_bp = Blueprint('irrigation', __name__)
api_bp.register_blueprint(irrigation_bp, url_prefix='/irrigation')

# Global controllers (will be initialized in app.py)
controllers = {}


@irrigation_bp.route('/start', methods=['POST'])
def start_irrigation():
    """Start irrigation for a zone."""
    try:
        data = request.get_json() or {}
        zone_id = data.get('zone_id')
        
        if not zone_id:
            return jsonify({
                'success': False,
                'error': 'zone_id is required'
            }), 400
        
        irrigation_ctrl = controllers.get('irrigation')
        if not irrigation_ctrl:
            return jsonify({
                'success': False,
                'error': 'Irrigation controller not initialized'
            }), 500
        
        # Get zone config (would normally come from database)
        zone_config = controllers.get('zone_configs', {}).get(zone_id)
        if not zone_config:
            return jsonify({
                'success': False,
                'error': f'Zone {zone_id} not configured'
            }), 404
        
        result = irrigation_ctrl.start_irrigation(zone_id, zone_config)
        
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

