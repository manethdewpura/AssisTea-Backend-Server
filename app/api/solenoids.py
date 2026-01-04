"""Solenoid status API endpoints."""
from flask import Blueprint, jsonify, request
from app.api import api_bp
from app.services.solenoid_state_manager import SolenoidStateManager

solenoids_bp = Blueprint('solenoids', __name__)
api_bp.register_blueprint(solenoids_bp, url_prefix='/solenoids')

# Global state manager (will be initialized in main.py)
state_manager: SolenoidStateManager = None


@solenoids_bp.route('/status', methods=['GET'])
def get_all_solenoid_status():
    """Get status of all solenoids."""
    try:
        if not state_manager:
            return jsonify({
                'success': False,
                'error': 'Solenoid state manager not initialized'
            }), 500
        
        states = state_manager.get_all_solenoid_states()
        
        # Get detailed info for each solenoid
        detailed_states = {}
        for solenoid_name in states.keys():
            info = state_manager.get_solenoid_info(solenoid_name)
            if info:
                detailed_states[solenoid_name] = info
        
        return jsonify({
            'success': True,
            'solenoids': detailed_states,
            'count': len(detailed_states)
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@solenoids_bp.route('/status/<solenoid_name>', methods=['GET'])
def get_solenoid_status(solenoid_name: str):
    """Get status of a specific solenoid."""
    try:
        if not state_manager:
            return jsonify({
                'success': False,
                'error': 'Solenoid state manager not initialized'
            }), 500
        
        info = state_manager.get_solenoid_info(solenoid_name)
        
        if info is None:
            return jsonify({
                'success': False,
                'error': f'Solenoid {solenoid_name} not found'
            }), 404
        
        return jsonify({
            'success': True,
            'solenoid': info
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@solenoids_bp.route('/status/<solenoid_name>', methods=['POST'])
def set_solenoid_status(solenoid_name: str):
    """Set status of a specific solenoid."""
    try:
        if not state_manager:
            return jsonify({
                'success': False,
                'error': 'Solenoid state manager not initialized'
            }), 500
        
        data = request.get_json() or {}
        is_open = data.get('is_open')
        
        if is_open is None:
            return jsonify({
                'success': False,
                'error': 'is_open parameter is required (true or false)'
            }), 400
        
        # Convert to boolean
        if isinstance(is_open, str):
            is_open = is_open.lower() in ('true', '1', 'yes', 'on')
        else:
            is_open = bool(is_open)
        
        success = state_manager.set_solenoid_state(solenoid_name, is_open)
        
        if success:
            info = state_manager.get_solenoid_info(solenoid_name)
            return jsonify({
                'success': True,
                'message': f'Solenoid {solenoid_name} set to {"open" if is_open else "closed"}',
                'solenoid': info
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': f'Failed to set solenoid {solenoid_name} state'
            }), 500
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

