"""Alert API endpoints."""
from flask import Blueprint, jsonify, request
from app.api import api_bp
from app.config.database import get_db
from app.models.system_log import SystemLog, LogLevel
from datetime import datetime, timedelta

alerts_bp = Blueprint('alerts', __name__)
api_bp.register_blueprint(alerts_bp, url_prefix='/alerts')

# In-memory alert tracking (could be moved to database)
active_alerts = {}


@alerts_bp.route('', methods=['GET'])
def get_alerts():
    """Get active alerts and errors."""
    try:
        db = next(get_db())
        
        # Get recent errors and warnings
        cutoff_time = datetime.now() - timedelta(hours=24)  # Last 24 hours
        
        errors = db.query(SystemLog).filter(
            SystemLog.log_level.in_([LogLevel.ERROR, LogLevel.CRITICAL]),
            SystemLog.timestamp >= cutoff_time
        ).order_by(SystemLog.timestamp.desc()).limit(50).all()
        
        warnings = db.query(SystemLog).filter(
            SystemLog.log_level == LogLevel.WARNING,
            SystemLog.timestamp >= cutoff_time
        ).order_by(SystemLog.timestamp.desc()).limit(50).all()
        
        error_list = [{
            'id': log.id,
            'timestamp': log.timestamp.isoformat() if log.timestamp else None,
            'log_level': log.log_level.value if log.log_level else None,
            'component': log.component,
            'message': log.message,
            'error_code': log.error_code,
            'zone_id': log.zone_id,
            'sensor_id': log.sensor_id
        } for log in errors]
        
        warning_list = [{
            'id': log.id,
            'timestamp': log.timestamp.isoformat() if log.timestamp else None,
            'log_level': log.log_level.value if log.log_level else None,
            'component': log.component,
            'message': log.message,
            'error_code': log.error_code,
            'zone_id': log.zone_id,
            'sensor_id': log.sensor_id
        } for log in warnings]
        
        db.close()
        
        return jsonify({
            'success': True,
            'alerts': {
                'errors': error_list,
                'warnings': warning_list,
                'active_alerts': list(active_alerts.values())
            },
            'counts': {
                'errors': len(error_list),
                'warnings': len(warning_list),
                'active': len(active_alerts)
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@alerts_bp.route('/<int:alert_id>/acknowledge', methods=['POST'])
def acknowledge_alert(alert_id):
    """Acknowledge an alert."""
    try:
        db = next(get_db())
        
        # Check if it's a system log entry
        log_entry = db.query(SystemLog).filter_by(id=alert_id).first()
        
        if log_entry:
            # Mark as acknowledged (could add acknowledged field to model)
            # For now, just remove from active alerts if present
            if alert_id in active_alerts:
                del active_alerts[alert_id]
        
        db.close()
        
        return jsonify({
            'success': True,
            'message': 'Alert acknowledged'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

