"""Zone configuration API endpoints."""
from flask import Blueprint, jsonify, request
from app.api import api_bp
from app.config.database import get_db
from app.models.zone import ZoneConfig

zones_bp = Blueprint('zones', __name__)
api_bp.register_blueprint(zones_bp, url_prefix='/zones')


@zones_bp.route('', methods=['GET'])
def list_zones():
    """List all zone configurations."""
    try:
        db = next(get_db())
        zones = db.query(ZoneConfig).all()
        
        result = [{
            'zone_id': z.zone_id,
            'name': z.name,
            'altitude': z.altitude,
            'slope': z.slope,
            'area': z.area,
            'base_pressure': z.base_pressure,
            'valve_gpio_pin': z.valve_gpio_pin,
            'pump_gpio_pin': z.pump_gpio_pin,
            'soil_moisture_sensor_pin': z.soil_moisture_sensor_pin,
            'pressure_sensor_pin': z.pressure_sensor_pin,
            'enabled': z.enabled,
        } for z in zones]
        
        db.close()
        return jsonify({
            'success': True,
            'zones': result
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@zones_bp.route('/<int:zone_id>', methods=['GET'])
def get_zone(zone_id):
    """Get a specific zone configuration."""
    try:
        db = next(get_db())
        zone = db.query(ZoneConfig).filter_by(zone_id=zone_id).first()
        
        if not zone:
            db.close()
            return jsonify({
                'success': False,
                'error': f'Zone {zone_id} not found'
            }), 404
        
        result = {
            'zone_id': zone.zone_id,
            'name': zone.name,
            'altitude': zone.altitude,
            'slope': zone.slope,
            'area': zone.area,
            'base_pressure': zone.base_pressure,
            'valve_gpio_pin': zone.valve_gpio_pin,
            'pump_gpio_pin': zone.pump_gpio_pin,
            'soil_moisture_sensor_pin': zone.soil_moisture_sensor_pin,
            'pressure_sensor_pin': zone.pressure_sensor_pin,
            'enabled': zone.enabled,
        }
        
        db.close()
        return jsonify({
            'success': True,
            'zone': result
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@zones_bp.route('', methods=['POST'])
def create_zone():
    """Create a new zone configuration."""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'Request body is required'
            }), 400
        
        required_fields = ['zone_id', 'name', 'altitude', 'slope', 'area', 'base_pressure', 'valve_gpio_pin']
        missing_fields = [field for field in required_fields if field not in data]
        
        if missing_fields:
            return jsonify({
                'success': False,
                'error': f'Missing required fields: {", ".join(missing_fields)}'
            }), 400
        
        db = next(get_db())
        
        # Check if zone already exists
        existing = db.query(ZoneConfig).filter_by(zone_id=data['zone_id']).first()
        if existing:
            db.close()
            return jsonify({
                'success': False,
                'error': f'Zone {data["zone_id"]} already exists'
            }), 400
        
        zone = ZoneConfig(
            zone_id=data['zone_id'],
            name=data['name'],
            altitude=float(data['altitude']),
            slope=float(data['slope']),
            area=float(data['area']),
            base_pressure=float(data['base_pressure']),
            valve_gpio_pin=int(data['valve_gpio_pin']),
            pump_gpio_pin=int(data['pump_gpio_pin']) if data.get('pump_gpio_pin') else None,
            soil_moisture_sensor_pin=int(data['soil_moisture_sensor_pin']) if data.get('soil_moisture_sensor_pin') else None,
            pressure_sensor_pin=int(data['pressure_sensor_pin']) if data.get('pressure_sensor_pin') else None,
            enabled=data.get('enabled', 'true')
        )
        
        db.add(zone)
        db.commit()
        zone_id = zone.zone_id
        db.close()
        
        return jsonify({
            'success': True,
            'message': 'Zone configuration created',
            'zone': {
                'zone_id': zone_id,
                'name': zone.name,
                'altitude': zone.altitude,
                'slope': zone.slope,
                'area': zone.area,
                'base_pressure': zone.base_pressure,
                'valve_gpio_pin': zone.valve_gpio_pin,
                'pump_gpio_pin': zone.pump_gpio_pin,
                'soil_moisture_sensor_pin': zone.soil_moisture_sensor_pin,
                'pressure_sensor_pin': zone.pressure_sensor_pin,
                'enabled': zone.enabled,
            }
        }), 201
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@zones_bp.route('/<int:zone_id>', methods=['PUT'])
def update_zone(zone_id):
    """Update a zone configuration."""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'Request body is required'
            }), 400
        
        db = next(get_db())
        zone = db.query(ZoneConfig).filter_by(zone_id=zone_id).first()
        
        if not zone:
            db.close()
            return jsonify({
                'success': False,
                'error': f'Zone {zone_id} not found'
            }), 404
        
        # Update fields if provided
        if 'name' in data:
            zone.name = data['name']
        if 'altitude' in data:
            zone.altitude = float(data['altitude'])
        if 'slope' in data:
            zone.slope = float(data['slope'])
        if 'area' in data:
            zone.area = float(data['area'])
        if 'base_pressure' in data:
            zone.base_pressure = float(data['base_pressure'])
        if 'valve_gpio_pin' in data:
            zone.valve_gpio_pin = int(data['valve_gpio_pin'])
        if 'pump_gpio_pin' in data:
            zone.pump_gpio_pin = int(data['pump_gpio_pin']) if data['pump_gpio_pin'] else None
        if 'soil_moisture_sensor_pin' in data:
            zone.soil_moisture_sensor_pin = int(data['soil_moisture_sensor_pin']) if data.get('soil_moisture_sensor_pin') else None
        if 'pressure_sensor_pin' in data:
            zone.pressure_sensor_pin = int(data['pressure_sensor_pin']) if data.get('pressure_sensor_pin') else None
        if 'enabled' in data:
            zone.enabled = data['enabled']
        
        db.commit()
        db.close()
        
        return jsonify({
            'success': True,
            'message': 'Zone configuration updated',
            'zone': {
                'zone_id': zone.zone_id,
                'name': zone.name,
                'altitude': zone.altitude,
                'slope': zone.slope,
                'area': zone.area,
                'base_pressure': zone.base_pressure,
                'valve_gpio_pin': zone.valve_gpio_pin,
                'pump_gpio_pin': zone.pump_gpio_pin,
                'soil_moisture_sensor_pin': zone.soil_moisture_sensor_pin,
                'pressure_sensor_pin': zone.pressure_sensor_pin,
                'enabled': zone.enabled,
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@zones_bp.route('/<int:zone_id>', methods=['DELETE'])
def delete_zone(zone_id):
    """Delete a zone configuration."""
    try:
        db = next(get_db())
        zone = db.query(ZoneConfig).filter_by(zone_id=zone_id).first()
        
        if not zone:
            db.close()
            return jsonify({
                'success': False,
                'error': f'Zone {zone_id} not found'
            }), 404
        
        db.delete(zone)
        db.commit()
        db.close()
        
        return jsonify({
            'success': True,
            'message': f'Zone {zone_id} deleted'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

