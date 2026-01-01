"""System control API endpoints."""
from flask import Blueprint, jsonify, request
from app.api import api_bp

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

