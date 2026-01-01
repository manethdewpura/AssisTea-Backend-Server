"""Log viewing API endpoints."""
from flask import Blueprint, jsonify, request
from app.api import api_bp
from app.config.database import get_db
from app.models.sensor_log import SensorLog, SensorType
from app.models.operational_log import OperationalLog, OperationType
from app.models.system_log import SystemLog, LogLevel
from datetime import datetime, timedelta

logs_bp = Blueprint('logs', __name__)
api_bp.register_blueprint(logs_bp, url_prefix='/logs')


@logs_bp.route('/sensor', methods=['GET'])
def get_sensor_logs():
    """Get sensor logs with optional filters."""
    try:
        db = next(get_db())
        
        # Get query parameters
        sensor_type = request.args.get('sensor_type')
        zone_id = request.args.get('zone_id', type=int)
        limit = request.args.get('limit', default=100, type=int)
        hours = request.args.get('hours', type=int)  # Last N hours
        
        query = db.query(SensorLog)
        
        if sensor_type:
            try:
                sensor_type_enum = SensorType[sensor_type.upper()]
                query = query.filter(SensorLog.sensor_type == sensor_type_enum)
            except KeyError:
                pass
        
        if zone_id:
            query = query.filter(SensorLog.zone_id == zone_id)
        
        if hours:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            query = query.filter(SensorLog.timestamp >= cutoff_time)
        
        logs = query.order_by(SensorLog.timestamp.desc()).limit(limit).all()
        
        result = [{
            'id': log.id,
            'timestamp': log.timestamp.isoformat() if log.timestamp else None,
            'sensor_type': log.sensor_type.value if log.sensor_type else None,
            'zone_id': log.zone_id,
            'value': log.value,
            'unit': log.unit,
            'raw_value': log.raw_value,
            'raw_unit': log.raw_unit
        } for log in logs]
        
        db.close()
        return jsonify({
            'success': True,
            'logs': result,
            'count': len(result)
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@logs_bp.route('/operational', methods=['GET'])
def get_operational_logs():
    """Get operational logs."""
    try:
        db = next(get_db())
        
        # Get query parameters
        operation_type = request.args.get('operation_type')
        zone_id = request.args.get('zone_id', type=int)
        limit = request.args.get('limit', default=100, type=int)
        hours = request.args.get('hours', type=int)
        
        query = db.query(OperationalLog)
        
        if operation_type:
            try:
                op_type_enum = OperationType[operation_type.upper()]
                query = query.filter(OperationalLog.operation_type == op_type_enum)
            except KeyError:
                pass
        
        if zone_id:
            query = query.filter(OperationalLog.zone_id == zone_id)
        
        if hours:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            query = query.filter(OperationalLog.timestamp >= cutoff_time)
        
        logs = query.order_by(OperationalLog.timestamp.desc()).limit(limit).all()
        
        result = [{
            'id': log.id,
            'timestamp': log.timestamp.isoformat() if log.timestamp else None,
            'operation_type': log.operation_type.value if log.operation_type else None,
            'zone_id': log.zone_id,
            'status': log.status.value if log.status else None,
            'duration': log.duration,
            'pressure': log.pressure,
            'flow_rate': log.flow_rate,
            'water_volume': log.water_volume,
            'fertilizer_volume': log.fertilizer_volume,
            'start_moisture': log.start_moisture,
            'end_moisture': log.end_moisture,
            'notes': log.notes
        } for log in logs]
        
        db.close()
        return jsonify({
            'success': True,
            'logs': result,
            'count': len(result)
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@logs_bp.route('/system', methods=['GET'])
def get_system_logs():
    """Get system logs."""
    try:
        db = next(get_db())
        
        # Get query parameters
        log_level = request.args.get('log_level')
        component = request.args.get('component')
        zone_id = request.args.get('zone_id', type=int)
        limit = request.args.get('limit', default=100, type=int)
        hours = request.args.get('hours', type=int)
        
        query = db.query(SystemLog)
        
        if log_level:
            try:
                level_enum = LogLevel[log_level.upper()]
                query = query.filter(SystemLog.log_level == level_enum)
            except KeyError:
                pass
        
        if component:
            query = query.filter(SystemLog.component == component)
        
        if zone_id:
            query = query.filter(SystemLog.zone_id == zone_id)
        
        if hours:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            query = query.filter(SystemLog.timestamp >= cutoff_time)
        
        logs = query.order_by(SystemLog.timestamp.desc()).limit(limit).all()
        
        result = [{
            'id': log.id,
            'timestamp': log.timestamp.isoformat() if log.timestamp else None,
            'log_level': log.log_level.value if log.log_level else None,
            'component': log.component,
            'message': log.message,
            'error_code': log.error_code,
            'zone_id': log.zone_id,
            'sensor_id': log.sensor_id
        } for log in logs]
        
        db.close()
        return jsonify({
            'success': True,
            'logs': result,
            'count': len(result)
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

