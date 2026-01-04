"""Schedule management API endpoints."""
from flask import Blueprint, jsonify, request
from app.api import api_bp
from app.config.database import get_db
from app.models.schedule import IrrigationSchedule, FertigationSchedule
from app.config.config import ZONE_ID
from datetime import time as dt_time

schedules_bp = Blueprint('schedules', __name__)
api_bp.register_blueprint(schedules_bp, url_prefix='/schedules')


@schedules_bp.route('/irrigation', methods=['GET'])
def list_irrigation_schedules():
    """List all irrigation schedules."""
    try:
        db = next(get_db())
        schedules = db.query(IrrigationSchedule).all()
        
        result = [{
            'id': s.id,
            'zone_id': s.zone_id,
            'day_of_week': s.day_of_week,
            'time': s.time.strftime('%H:%M:%S') if s.time else None,
            'enabled': s.enabled,
            'last_run': s.last_run.isoformat() if s.last_run else None
        } for s in schedules]
        
        db.close()
        return jsonify({
            'success': True,
            'schedules': result
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@schedules_bp.route('/irrigation', methods=['POST'])
def create_irrigation_schedule():
    """Create a new irrigation schedule."""
    try:
        data = request.get_json()
        
        if not data or not all(k in data for k in ['day_of_week', 'time']):
            return jsonify({
                'success': False,
                'error': 'day_of_week and time are required'
            }), 400
        
        db = next(get_db())
        
        # Parse time string (HH:MM:SS or HH:MM)
        time_str = data['time']
        time_parts = time_str.split(':')
        schedule_time = dt_time(int(time_parts[0]), int(time_parts[1]), int(time_parts[2]) if len(time_parts) > 2 else 0)
        
        schedule = IrrigationSchedule(
            zone_id=ZONE_ID,
            day_of_week=data['day_of_week'],
            time=schedule_time,
            enabled=data.get('enabled', True)
        )
        
        db.add(schedule)
        db.commit()
        schedule_id = schedule.id
        db.close()
        
        return jsonify({
            'success': True,
            'message': 'Irrigation schedule created',
            'id': schedule_id
        }), 201
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@schedules_bp.route('/irrigation/<int:schedule_id>', methods=['PUT'])
def update_irrigation_schedule(schedule_id):
    """Update an irrigation schedule."""
    try:
        data = request.get_json()
        db = next(get_db())
        
        schedule = db.query(IrrigationSchedule).filter_by(id=schedule_id).first()
        if not schedule:
            db.close()
            return jsonify({
                'success': False,
                'error': 'Schedule not found'
            }), 404
        
        # zone_id is always ZONE_ID (hardcoded to 1)
        schedule.zone_id = ZONE_ID
        if 'day_of_week' in data:
            schedule.day_of_week = data['day_of_week']
        if 'time' in data:
            time_str = data['time']
            time_parts = time_str.split(':')
            schedule.time = dt_time(int(time_parts[0]), int(time_parts[1]), int(time_parts[2]) if len(time_parts) > 2 else 0)
        if 'enabled' in data:
            schedule.enabled = data['enabled']
        
        db.commit()
        db.close()
        
        return jsonify({
            'success': True,
            'message': 'Schedule updated'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@schedules_bp.route('/irrigation/<int:schedule_id>', methods=['DELETE'])
def delete_irrigation_schedule(schedule_id):
    """Delete an irrigation schedule."""
    try:
        db = next(get_db())
        schedule = db.query(IrrigationSchedule).filter_by(id=schedule_id).first()
        
        if not schedule:
            db.close()
            return jsonify({
                'success': False,
                'error': 'Schedule not found'
            }), 404
        
        db.delete(schedule)
        db.commit()
        db.close()
        
        return jsonify({
            'success': True,
            'message': 'Schedule deleted'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# Fertigation schedules (similar endpoints)
@schedules_bp.route('/fertigation', methods=['GET'])
def list_fertigation_schedules():
    """List all fertigation schedules."""
    try:
        db = next(get_db())
        schedules = db.query(FertigationSchedule).all()
        
        result = [{
            'id': s.id,
            'zone_id': s.zone_id,
            'day_of_week': s.day_of_week,
            'time': s.time.strftime('%H:%M:%S') if s.time else None,
            'enabled': s.enabled,
            'last_run': s.last_run.isoformat() if s.last_run else None
        } for s in schedules]
        
        db.close()
        return jsonify({
            'success': True,
            'schedules': result
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@schedules_bp.route('/fertigation', methods=['POST'])
def create_fertigation_schedule():
    """Create a new fertigation schedule."""
    try:
        data = request.get_json()
        
        if not data or not all(k in data for k in ['day_of_week', 'time']):
            return jsonify({
                'success': False,
                'error': 'day_of_week and time are required'
            }), 400
        
        db = next(get_db())
        
        time_str = data['time']
        time_parts = time_str.split(':')
        schedule_time = dt_time(int(time_parts[0]), int(time_parts[1]), int(time_parts[2]) if len(time_parts) > 2 else 0)
        
        schedule = FertigationSchedule(
            zone_id=ZONE_ID,
            day_of_week=data['day_of_week'],
            time=schedule_time,
            enabled=data.get('enabled', True)
        )
        
        db.add(schedule)
        db.commit()
        schedule_id = schedule.id
        db.close()
        
        return jsonify({
            'success': True,
            'message': 'Fertigation schedule created',
            'id': schedule_id
        }), 201
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@schedules_bp.route('/fertigation/<int:schedule_id>', methods=['PUT'])
def update_fertigation_schedule(schedule_id):
    """Update a fertigation schedule."""
    try:
        data = request.get_json()
        db = next(get_db())
        
        schedule = db.query(FertigationSchedule).filter_by(id=schedule_id).first()
        if not schedule:
            db.close()
            return jsonify({
                'success': False,
                'error': 'Schedule not found'
            }), 404
        
        # zone_id is always ZONE_ID (hardcoded to 1)
        schedule.zone_id = ZONE_ID
        if 'day_of_week' in data:
            schedule.day_of_week = data['day_of_week']
        if 'time' in data:
            time_str = data['time']
            time_parts = time_str.split(':')
            schedule.time = dt_time(int(time_parts[0]), int(time_parts[1]), int(time_parts[2]) if len(time_parts) > 2 else 0)
        if 'enabled' in data:
            schedule.enabled = data['enabled']
        
        db.commit()
        db.close()
        
        return jsonify({
            'success': True,
            'message': 'Schedule updated'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@schedules_bp.route('/fertigation/<int:schedule_id>', methods=['DELETE'])
def delete_fertigation_schedule(schedule_id):
    """Delete a fertigation schedule."""
    try:
        db = next(get_db())
        schedule = db.query(FertigationSchedule).filter_by(id=schedule_id).first()
        
        if not schedule:
            db.close()
            return jsonify({
                'success': False,
                'error': 'Schedule not found'
            }), 404
        
        db.delete(schedule)
        db.commit()
        db.close()
        
        return jsonify({
            'success': True,
            'message': 'Schedule deleted'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

