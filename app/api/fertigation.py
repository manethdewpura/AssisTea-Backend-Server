"""Fertigation API endpoints."""
from flask import Blueprint, jsonify, request
from app.api import api_bp
from app.config.config import ZONE_ID

fertigation_bp = Blueprint('fertigation', __name__)
api_bp.register_blueprint(fertigation_bp, url_prefix='/fertigation')

# Global controllers (will be initialized in app.py)
controllers = {}


@fertigation_bp.route('/start', methods=['POST'])
def start_fertigation():
    """Start fertigation for the system zone."""
    try:
        fertigation_ctrl = controllers.get('fertigation')
        if not fertigation_ctrl:
            return jsonify({
                'success': False,
                'error': 'Fertigation controller not initialized'
            }), 500
        
        result = fertigation_ctrl.start_fertigation(ZONE_ID)
        
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@fertigation_bp.route('/stop', methods=['POST'])
def stop_fertigation():
    """Stop current fertigation."""
    try:
        fertigation_ctrl = controllers.get('fertigation')
        if not fertigation_ctrl:
            return jsonify({
                'success': False,
                'error': 'Fertigation controller not initialized'
            }), 500
        
        result = fertigation_ctrl.stop_fertigation()
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@fertigation_bp.route('/status', methods=['GET'])
def get_fertigation_status():
    """Get fertigation status."""
    try:
        fertigation_ctrl = controllers.get('fertigation')
        if not fertigation_ctrl:
            return jsonify({
                'success': False,
                'error': 'Fertigation controller not initialized'
            }), 500
        
        status = fertigation_ctrl.get_status()
        return jsonify({
            'success': True,
            'status': status
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

