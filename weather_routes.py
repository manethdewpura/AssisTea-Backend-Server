from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
from database import db, WeatherCurrent, WeatherForecast, build_historical_data_for_prediction
from ml_predictor import get_predictor, is_ml_available
from sqlalchemy.exc import IntegrityError
import json
import logging

logger = logging.getLogger(__name__)

weather_bp = Blueprint('weather', __name__, url_prefix='/weather')


def extract_weather_data(weather_data):
    """Extract weather condition data"""
    if weather_data and len(weather_data) > 0:
        return {
            'main': weather_data[0].get('main', ''),
            'description': weather_data[0].get('description', ''),
            'icon': weather_data[0].get('icon', '')
        }
    return {'main': '', 'description': '', 'icon': ''}


@weather_bp.route('/current', methods=['POST'])
def sync_current_weather():
    """Sync current weather data to database (appends records to maintain historical data)"""
    try:
        data = request.json
        
        if not data or 'data' not in data:
            return jsonify({
                'success': False,
                'message': 'Invalid request: missing data field'
            }), 400
        
        weather_data = data['data']
        timestamp = data.get('timestamp', int(datetime.utcnow().timestamp() * 1000))  # Sync timestamp from mobile app
        
        measured_at = weather_data.get('dt')
        if measured_at:
            measured_at_ms = int(measured_at * 1000)  
        else:
            # Fallback: use current time if dt not available
            measured_at_ms = int(datetime.utcnow().timestamp() * 1000)
        
        # Extract weather condition
        weather_condition = extract_weather_data(weather_data.get('weather', []))
        
        location_id = weather_data.get('id')
        
        # Validate required fields
        coord = weather_data.get('coord', {})
        if not coord.get('lon') or not coord.get('lat'):
            return jsonify({
                'success': False,
                'message': 'Invalid request: missing coordinates (lon/lat)'
            }), 400
        
        # Check for duplicate: same location, same measurement time (within 1 hour window),
        # AND same sync timestamp (within 30 minutes) - this prevents true duplicates while
        # allowing queued data with same measured_at but different fetch times (1+ hours apart)
        measured_time_window_ms = 3600000  # 1 hour in milliseconds
        sync_time_window_ms = 1800000  # 30 minutes in milliseconds (less than 1-hour fetch interval)
        query = WeatherCurrent.query
        if location_id is not None:
            query = query.filter_by(location_id=location_id)
        else:
            query = query.filter(WeatherCurrent.location_id.is_(None))
        
        # First check for exact match on (location_id, measured_at) to handle unique constraint
        exact_match = query.filter(
            WeatherCurrent.measured_at == measured_at_ms
        ).first()
        
        if exact_match:
            # Exact match found - update it (preserves unique constraint)
            existing_record = exact_match
        else:
            # Check for duplicate using range checks (for time-window duplicates)
            existing_record = query.filter(
                WeatherCurrent.measured_at.isnot(None),
                WeatherCurrent.measured_at >= (measured_at_ms - measured_time_window_ms),
                WeatherCurrent.measured_at <= (measured_at_ms + measured_time_window_ms),
                WeatherCurrent.timestamp >= (timestamp - sync_time_window_ms),
                WeatherCurrent.timestamp <= (timestamp + sync_time_window_ms)
            ).first()
        
        if existing_record:
            # Update existing record instead of creating duplicate
            # DO NOT update timestamp - keep original to preserve historical accuracy
            existing_record.synced_at = datetime.utcnow()
            existing_record.measured_at = measured_at_ms
            existing_record.coord_lon = weather_data.get('coord', {}).get('lon', 0)
            existing_record.coord_lat = weather_data.get('coord', {}).get('lat', 0)
            existing_record.location_name = weather_data.get('name', '')
            existing_record.timezone = weather_data.get('timezone')
            existing_record.weather_main = weather_condition['main']
            existing_record.weather_description = weather_condition['description']
            existing_record.weather_icon = weather_condition['icon']
            existing_record.temp = weather_data.get('main', {}).get('temp')
            existing_record.feels_like = weather_data.get('main', {}).get('feels_like')
            existing_record.temp_min = weather_data.get('main', {}).get('temp_min')
            existing_record.temp_max = weather_data.get('main', {}).get('temp_max')
            existing_record.pressure = weather_data.get('main', {}).get('pressure')
            existing_record.humidity = weather_data.get('main', {}).get('humidity')
            existing_record.wind_speed = weather_data.get('wind', {}).get('speed')
            existing_record.wind_deg = weather_data.get('wind', {}).get('deg')
            existing_record.wind_gust = weather_data.get('wind', {}).get('gust')
            existing_record.visibility = weather_data.get('visibility')
            existing_record.clouds_all = weather_data.get('clouds', {}).get('all')
            existing_record.rain_1h = weather_data.get('rain', {}).get('1h') if weather_data.get('rain') else None
            existing_record.rain_3h = weather_data.get('rain', {}).get('3h') if weather_data.get('rain') else None
            existing_record.country = weather_data.get('sys', {}).get('country', '')
            existing_record.raw_data = json.dumps(weather_data)
            
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': 'Current weather data updated (duplicate prevented)',
                'syncedAt': int(datetime.utcnow().timestamp() * 1000),
                'recordId': existing_record.id,
                'isUpdate': True
            }), 200
        
        # Clean up old records (keep last 10 days for efficiency)
        # This prevents database from growing indefinitely
        cutoff_time = int((datetime.utcnow() - timedelta(days=10)).timestamp() * 1000)
        if location_id:
            WeatherCurrent.query.filter_by(location_id=location_id).filter(
                WeatherCurrent.timestamp < cutoff_time
            ).delete()
        else:
            WeatherCurrent.query.filter(WeatherCurrent.timestamp < cutoff_time).delete()
        
        # Create new current weather record 
        try:
            weather_record = WeatherCurrent(
                timestamp=timestamp,  
                measured_at=measured_at_ms,  
                coord_lon=weather_data.get('coord', {}).get('lon', 0),
                coord_lat=weather_data.get('coord', {}).get('lat', 0),
                location_name=weather_data.get('name', ''),
                location_id=location_id,
                timezone=weather_data.get('timezone'),
                weather_main=weather_condition['main'],
                weather_description=weather_condition['description'],
                weather_icon=weather_condition['icon'],
                temp=weather_data.get('main', {}).get('temp'),
                feels_like=weather_data.get('main', {}).get('feels_like'),
                temp_min=weather_data.get('main', {}).get('temp_min'),
                temp_max=weather_data.get('main', {}).get('temp_max'),
                pressure=weather_data.get('main', {}).get('pressure'),
                humidity=weather_data.get('main', {}).get('humidity'),
                wind_speed=weather_data.get('wind', {}).get('speed'),
                wind_deg=weather_data.get('wind', {}).get('deg'),
                wind_gust=weather_data.get('wind', {}).get('gust'),
                visibility=weather_data.get('visibility'),
                clouds_all=weather_data.get('clouds', {}).get('all'),
                rain_1h=weather_data.get('rain', {}).get('1h') if weather_data.get('rain') else None,
                rain_3h=weather_data.get('rain', {}).get('3h') if weather_data.get('rain') else None,
                country=weather_data.get('sys', {}).get('country', ''),
                raw_data=json.dumps(weather_data)
            )
            
            db.session.add(weather_record)
            db.session.commit()
        except IntegrityError:
            # Handle unique constraint violation - record with same (location_id, measured_at) exists
            db.session.rollback()
            # Re-query to get the existing record
            existing_record = query.filter(
                WeatherCurrent.measured_at == measured_at_ms
            ).first()
            if existing_record:
                # Update the existing record
                existing_record.synced_at = datetime.utcnow()
                existing_record.coord_lon = weather_data.get('coord', {}).get('lon', 0)
                existing_record.coord_lat = weather_data.get('coord', {}).get('lat', 0)
                existing_record.location_name = weather_data.get('name', '')
                existing_record.timezone = weather_data.get('timezone')
                existing_record.weather_main = weather_condition['main']
                existing_record.weather_description = weather_condition['description']
                existing_record.weather_icon = weather_condition['icon']
                existing_record.temp = weather_data.get('main', {}).get('temp')
                existing_record.feels_like = weather_data.get('main', {}).get('feels_like')
                existing_record.temp_min = weather_data.get('main', {}).get('temp_min')
                existing_record.temp_max = weather_data.get('main', {}).get('temp_max')
                existing_record.pressure = weather_data.get('main', {}).get('pressure')
                existing_record.humidity = weather_data.get('main', {}).get('humidity')
                existing_record.wind_speed = weather_data.get('wind', {}).get('speed')
                existing_record.wind_deg = weather_data.get('wind', {}).get('deg')
                existing_record.wind_gust = weather_data.get('wind', {}).get('gust')
                existing_record.visibility = weather_data.get('visibility')
                existing_record.clouds_all = weather_data.get('clouds', {}).get('all')
                existing_record.rain_1h = weather_data.get('rain', {}).get('1h') if weather_data.get('rain') else None
                existing_record.rain_3h = weather_data.get('rain', {}).get('3h') if weather_data.get('rain') else None
                existing_record.country = weather_data.get('sys', {}).get('country', '')
                existing_record.raw_data = json.dumps(weather_data)
                db.session.commit()
                weather_record = existing_record
            else:
                raise
        
        return jsonify({
            'success': True,
            'message': 'Current weather data synced (historical data maintained)',
            'syncedAt': int(datetime.utcnow().timestamp() * 1000),
            'recordId': weather_record.id
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error syncing current weather: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'message': f'Error syncing current weather: {str(e)}'
        }), 500


@weather_bp.route('/forecast', methods=['POST'])
def sync_weather_forecast():
    """Sync weather forecast data to database (UPSERT: Update existing or Insert new)"""
    try:
        data = request.json
        
        if not data or 'data' not in data:
            return jsonify({
                'success': False,
                'message': 'Invalid request: missing data field'
            }), 400
        
        forecast_data = data['data']
        timestamp = data.get('timestamp', int(datetime.utcnow().timestamp() * 1000))
        
        city_data = forecast_data.get('city', {})
        forecast_list = forecast_data.get('list', [])
        
        records_updated = 0
        records_created = 0
        
        # Store each forecast item with UPSERT logic
        for item in forecast_list:
            weather_condition = extract_weather_data(item.get('weather', []))
            
            forecast_dt = item.get('dt')
            city_id = city_data.get('id')
            
            # Check if this forecast already exists
            existing = WeatherForecast.query.filter_by(
                city_id=city_id,
                forecast_dt=forecast_dt
            ).first()
            
            if existing:
                # UPDATE existing record
                existing.timestamp = timestamp
                existing.synced_at = datetime.utcnow()
                existing.forecast_dt_txt = item.get('dt_txt', '')
                existing.city_name = city_data.get('name', '')
                existing.city_country = city_data.get('country', '')
                existing.city_coord_lat = city_data.get('coord', {}).get('lat')
                existing.city_coord_lon = city_data.get('coord', {}).get('lon')
                existing.city_timezone = city_data.get('timezone')
                existing.city_population = city_data.get('population')
                existing.weather_main = weather_condition['main']
                existing.weather_description = weather_condition['description']
                existing.weather_icon = weather_condition['icon']
                existing.temp = item.get('main', {}).get('temp')
                existing.feels_like = item.get('main', {}).get('feels_like')
                existing.temp_min = item.get('main', {}).get('temp_min')
                existing.temp_max = item.get('main', {}).get('temp_max')
                existing.pressure = item.get('main', {}).get('pressure')
                existing.humidity = item.get('main', {}).get('humidity')
                existing.wind_speed = item.get('wind', {}).get('speed')
                existing.wind_deg = item.get('wind', {}).get('deg')
                existing.wind_gust = item.get('wind', {}).get('gust')
                existing.visibility = item.get('visibility')
                existing.clouds_all = item.get('clouds', {}).get('all')
                existing.pop = item.get('pop', 0)
                existing.rain_1h = item.get('rain', {}).get('1h') if item.get('rain') else None
                existing.rain_3h = item.get('rain', {}).get('3h') if item.get('rain') else None
                existing.raw_data = json.dumps(item)
                
                records_updated += 1
            else:
                # INSERT new record
                forecast_record = WeatherForecast(
                    timestamp=timestamp,
                    forecast_dt=forecast_dt,
                    forecast_dt_txt=item.get('dt_txt', ''),
                    city_id=city_id,
                    city_name=city_data.get('name', ''),
                    city_country=city_data.get('country', ''),
                    city_coord_lat=city_data.get('coord', {}).get('lat'),
                    city_coord_lon=city_data.get('coord', {}).get('lon'),
                    city_timezone=city_data.get('timezone'),
                    city_population=city_data.get('population'),
                    weather_main=weather_condition['main'],
                    weather_description=weather_condition['description'],
                    weather_icon=weather_condition['icon'],
                    temp=item.get('main', {}).get('temp'),
                    feels_like=item.get('main', {}).get('feels_like'),
                    temp_min=item.get('main', {}).get('temp_min'),
                    temp_max=item.get('main', {}).get('temp_max'),
                    pressure=item.get('main', {}).get('pressure'),
                    humidity=item.get('main', {}).get('humidity'),
                    wind_speed=item.get('wind', {}).get('speed'),
                    wind_deg=item.get('wind', {}).get('deg'),
                    wind_gust=item.get('wind', {}).get('gust'),
                    visibility=item.get('visibility'),
                    clouds_all=item.get('clouds', {}).get('all'),
                    pop=item.get('pop', 0),
                    rain_1h=item.get('rain', {}).get('1h') if item.get('rain') else None,
                    rain_3h=item.get('rain', {}).get('3h') if item.get('rain') else None,
                    raw_data=json.dumps(item)
                )
                
                db.session.add(forecast_record)
                records_created += 1
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Forecast synced: {records_created} created, {records_updated} updated',
            'syncedAt': int(datetime.utcnow().timestamp() * 1000),
            'recordsCreated': records_created,
            'recordsUpdated': records_updated
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error syncing weather forecast: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'message': f'Error syncing weather forecast: {str(e)}'
        }), 500


@weather_bp.route('/sync', methods=['POST'])
def sync_all_weather_data():
    """Sync both current weather and forecast data"""
    try:
        data = request.json
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'Invalid request: missing data'
            }), 400
        
        timestamp = data.get('timestamp', int(datetime.utcnow().timestamp() * 1000))
        # Ensure timestamp is an integer
        if not isinstance(timestamp, (int, float)):
            timestamp = int(datetime.utcnow().timestamp() * 1000)
        else:
            timestamp = int(timestamp)
        
        current_data = data.get('current')
        forecast_data = data.get('forecast')
        
        results = {
            'current': None,
            'forecast': None
        }
        
        # Sync current weather if provided
        if current_data:
            weather_condition = extract_weather_data(current_data.get('weather', []))
            
            # Extract actual weather measurement time from API (dt field)
            measured_at = current_data.get('dt')
            if measured_at:
                measured_at_ms = int(measured_at * 1000)  
            else:
                measured_at_ms = int(datetime.utcnow().timestamp() * 1000)
            
            location_id = current_data.get('id')
            
            # Validate required fields
            coord = current_data.get('coord', {})
            if not coord.get('lon') or not coord.get('lat'):
                results['current'] = {'success': False, 'error': 'Missing coordinates'}
            else:
                # Check for duplicate: same location, same measurement time (within 1 hour window),
                # AND same sync timestamp (within 30 minutes) - this prevents true duplicates while
                # allowing queued data with same measured_at but different fetch times (1+ hours apart)
                measured_time_window_ms = 3600000  # 1 hour in milliseconds
                sync_time_window_ms = 1800000  # 30 minutes in milliseconds (less than 1-hour fetch interval)
                query = WeatherCurrent.query
                if location_id is not None:
                    query = query.filter_by(location_id=location_id)
                else:
                    query = query.filter(WeatherCurrent.location_id.is_(None))
                
                # First check for exact match on (location_id, measured_at) to handle unique constraint
                exact_match = query.filter(
                    WeatherCurrent.measured_at == measured_at_ms
                ).first()
                
                if exact_match:
                    # Exact match found - update it (preserves unique constraint)
                    existing_record = exact_match
                else:
                    # Check for duplicate using range checks (for time-window duplicates)
                    existing_record = query.filter(
                        WeatherCurrent.measured_at.isnot(None),
                        WeatherCurrent.measured_at >= (measured_at_ms - measured_time_window_ms),
                        WeatherCurrent.measured_at <= (measured_at_ms + measured_time_window_ms),
                        WeatherCurrent.timestamp >= (timestamp - sync_time_window_ms),
                        WeatherCurrent.timestamp <= (timestamp + sync_time_window_ms)
                    ).first()
                
                if existing_record:
                    # Update existing record instead of creating duplicate
                    # DO NOT update timestamp - keep original to preserve historical accuracy
                    existing_record.synced_at = datetime.utcnow()
                    existing_record.measured_at = measured_at_ms
                    existing_record.coord_lon = current_data.get('coord', {}).get('lon', 0)
                    existing_record.coord_lat = current_data.get('coord', {}).get('lat', 0)
                    existing_record.location_name = current_data.get('name', '')
                    existing_record.timezone = current_data.get('timezone')
                    existing_record.weather_main = weather_condition['main']
                    existing_record.weather_description = weather_condition['description']
                    existing_record.weather_icon = weather_condition['icon']
                    existing_record.temp = current_data.get('main', {}).get('temp')
                    existing_record.feels_like = current_data.get('main', {}).get('feels_like')
                    existing_record.temp_min = current_data.get('main', {}).get('temp_min')
                    existing_record.temp_max = current_data.get('main', {}).get('temp_max')
                    existing_record.pressure = current_data.get('main', {}).get('pressure')
                    existing_record.humidity = current_data.get('main', {}).get('humidity')
                    existing_record.wind_speed = current_data.get('wind', {}).get('speed')
                    existing_record.wind_deg = current_data.get('wind', {}).get('deg')
                    existing_record.wind_gust = current_data.get('wind', {}).get('gust')
                    existing_record.visibility = current_data.get('visibility')
                    existing_record.clouds_all = current_data.get('clouds', {}).get('all')
                    existing_record.rain_1h = current_data.get('rain', {}).get('1h') if current_data.get('rain') else None
                    existing_record.rain_3h = current_data.get('rain', {}).get('3h') if current_data.get('rain') else None
                    existing_record.country = current_data.get('sys', {}).get('country', '')
                    existing_record.raw_data = json.dumps(current_data)
                    
                    results['current'] = {'id': existing_record.id, 'success': True, 'isUpdate': True}
                else:
                    # Clean up old records (keep last 10 days for efficiency)
                    cutoff_time = int((datetime.utcnow() - timedelta(days=10)).timestamp() * 1000)
                    if location_id:
                        WeatherCurrent.query.filter_by(location_id=location_id).filter(
                            WeatherCurrent.timestamp < cutoff_time
                        ).delete()
                    else:
                        WeatherCurrent.query.filter(WeatherCurrent.timestamp < cutoff_time).delete()
                    
                    try:
                        weather_record = WeatherCurrent(
                            timestamp=timestamp,  
                            measured_at=measured_at_ms,  
                            coord_lon=current_data.get('coord', {}).get('lon', 0),
                            coord_lat=current_data.get('coord', {}).get('lat', 0),
                            location_name=current_data.get('name', ''),
                            location_id=location_id,
                            timezone=current_data.get('timezone'),
                            weather_main=weather_condition['main'],
                            weather_description=weather_condition['description'],
                            weather_icon=weather_condition['icon'],
                            temp=current_data.get('main', {}).get('temp'),
                            feels_like=current_data.get('main', {}).get('feels_like'),
                            temp_min=current_data.get('main', {}).get('temp_min'),
                            temp_max=current_data.get('main', {}).get('temp_max'),
                            pressure=current_data.get('main', {}).get('pressure'),
                            humidity=current_data.get('main', {}).get('humidity'),
                            wind_speed=current_data.get('wind', {}).get('speed'),
                            wind_deg=current_data.get('wind', {}).get('deg'),
                            wind_gust=current_data.get('wind', {}).get('gust'),
                            visibility=current_data.get('visibility'),
                            clouds_all=current_data.get('clouds', {}).get('all'),
                            rain_1h=current_data.get('rain', {}).get('1h') if current_data.get('rain') else None,
                            rain_3h=current_data.get('rain', {}).get('3h') if current_data.get('rain') else None,
                            country=current_data.get('sys', {}).get('country', ''),
                            raw_data=json.dumps(current_data)
                        )
                        
                        db.session.add(weather_record)
                        db.session.commit()
                        results['current'] = {'id': weather_record.id, 'success': True, 'isUpdate': False}
                    except IntegrityError:
                        # Handle unique constraint violation - record with same (location_id, measured_at) exists
                        db.session.rollback()
                        # Re-query to get the existing record
                        existing_record = query.filter(
                            WeatherCurrent.measured_at == measured_at_ms
                        ).first()
                        if existing_record:
                            # Update the existing record
                            existing_record.synced_at = datetime.utcnow()
                            existing_record.coord_lon = current_data.get('coord', {}).get('lon', 0)
                            existing_record.coord_lat = current_data.get('coord', {}).get('lat', 0)
                            existing_record.location_name = current_data.get('name', '')
                            existing_record.timezone = current_data.get('timezone')
                            existing_record.weather_main = weather_condition['main']
                            existing_record.weather_description = weather_condition['description']
                            existing_record.weather_icon = weather_condition['icon']
                            existing_record.temp = current_data.get('main', {}).get('temp')
                            existing_record.feels_like = current_data.get('main', {}).get('feels_like')
                            existing_record.temp_min = current_data.get('main', {}).get('temp_min')
                            existing_record.temp_max = current_data.get('main', {}).get('temp_max')
                            existing_record.pressure = current_data.get('main', {}).get('pressure')
                            existing_record.humidity = current_data.get('main', {}).get('humidity')
                            existing_record.wind_speed = current_data.get('wind', {}).get('speed')
                            existing_record.wind_deg = current_data.get('wind', {}).get('deg')
                            existing_record.wind_gust = current_data.get('wind', {}).get('gust')
                            existing_record.visibility = current_data.get('visibility')
                            existing_record.clouds_all = current_data.get('clouds', {}).get('all')
                            existing_record.rain_1h = current_data.get('rain', {}).get('1h') if current_data.get('rain') else None
                            existing_record.rain_3h = current_data.get('rain', {}).get('3h') if current_data.get('rain') else None
                            existing_record.country = current_data.get('sys', {}).get('country', '')
                            existing_record.raw_data = json.dumps(current_data)
                            db.session.commit()
                            results['current'] = {'id': existing_record.id, 'success': True, 'isUpdate': True}
                        else:
                            raise
        
        # Sync forecast if provided
        if forecast_data:
            city_data = forecast_data.get('city', {})
            forecast_list = forecast_data.get('list', [])
            
            forecast_created = 0
            forecast_updated = 0
            
            for item in forecast_list:
                weather_condition = extract_weather_data(item.get('weather', []))
                
                forecast_dt = item.get('dt')
                city_id = city_data.get('id')
                
                # Check if this forecast already exists
                existing = WeatherForecast.query.filter_by(
                    city_id=city_id,
                    forecast_dt=forecast_dt
                ).first()
                
                if existing:
                    # UPDATE existing record
                    existing.timestamp = timestamp
                    existing.synced_at = datetime.utcnow()
                    existing.forecast_dt_txt = item.get('dt_txt', '')
                    existing.city_name = city_data.get('name', '')
                    existing.city_country = city_data.get('country', '')
                    existing.city_coord_lat = city_data.get('coord', {}).get('lat')
                    existing.city_coord_lon = city_data.get('coord', {}).get('lon')
                    existing.city_timezone = city_data.get('timezone')
                    existing.city_population = city_data.get('population')
                    existing.weather_main = weather_condition['main']
                    existing.weather_description = weather_condition['description']
                    existing.weather_icon = weather_condition['icon']
                    existing.temp = item.get('main', {}).get('temp')
                    existing.feels_like = item.get('main', {}).get('feels_like')
                    existing.temp_min = item.get('main', {}).get('temp_min')
                    existing.temp_max = item.get('main', {}).get('temp_max')
                    existing.pressure = item.get('main', {}).get('pressure')
                    existing.humidity = item.get('main', {}).get('humidity')
                    existing.wind_speed = item.get('wind', {}).get('speed')
                    existing.wind_deg = item.get('wind', {}).get('deg')
                    existing.wind_gust = item.get('wind', {}).get('gust')
                    existing.visibility = item.get('visibility')
                    existing.clouds_all = item.get('clouds', {}).get('all')
                    existing.pop = item.get('pop', 0)
                    existing.rain_1h = item.get('rain', {}).get('1h') if item.get('rain') else None
                    existing.rain_3h = item.get('rain', {}).get('3h') if item.get('rain') else None
                    existing.raw_data = json.dumps(item)
                    
                    forecast_updated += 1
                else:
                    # INSERT new record
                    forecast_record = WeatherForecast(
                        timestamp=timestamp,
                        forecast_dt=forecast_dt,
                        forecast_dt_txt=item.get('dt_txt', ''),
                        city_id=city_id,
                        city_name=city_data.get('name', ''),
                        city_country=city_data.get('country', ''),
                        city_coord_lat=city_data.get('coord', {}).get('lat'),
                        city_coord_lon=city_data.get('coord', {}).get('lon'),
                        city_timezone=city_data.get('timezone'),
                        city_population=city_data.get('population'),
                        weather_main=weather_condition['main'],
                        weather_description=weather_condition['description'],
                        weather_icon=weather_condition['icon'],
                        temp=item.get('main', {}).get('temp'),
                        feels_like=item.get('main', {}).get('feels_like'),
                        temp_min=item.get('main', {}).get('temp_min'),
                        temp_max=item.get('main', {}).get('temp_max'),
                        pressure=item.get('main', {}).get('pressure'),
                        humidity=item.get('main', {}).get('humidity'),
                        wind_speed=item.get('wind', {}).get('speed'),
                        wind_deg=item.get('wind', {}).get('deg'),
                        wind_gust=item.get('wind', {}).get('gust'),
                        visibility=item.get('visibility'),
                        clouds_all=item.get('clouds', {}).get('all'),
                        pop=item.get('pop', 0),
                        rain_1h=item.get('rain', {}).get('1h') if item.get('rain') else None,
                        rain_3h=item.get('rain', {}).get('3h') if item.get('rain') else None,
                        raw_data=json.dumps(item)
                    )
                    
                    db.session.add(forecast_record)
                    forecast_created += 1
            
            results['forecast'] = {
                'created': forecast_created,
                'updated': forecast_updated,
                'success': True
            }
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Weather data synced successfully',
            'syncedAt': int(datetime.utcnow().timestamp() * 1000),
            'results': results
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error syncing weather data: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'message': f'Error syncing weather data: {str(e)}'
        }), 500


@weather_bp.route('/current/latest', methods=['GET'])
def get_latest_current_weather():
    """Get the latest current weather data"""
    try:
        latest = WeatherCurrent.query.order_by(WeatherCurrent.timestamp.desc()).first()
        
        if not latest:
            return jsonify({
                'success': False,
                'message': 'No weather data found'
            }), 404
        
        return jsonify({
            'success': True,
            'data': latest.to_dict()
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error retrieving weather data: {str(e)}'
        }), 500


@weather_bp.route('/forecast/latest', methods=['GET'])
def get_latest_forecast():
    """Get the latest forecast data"""
    try:
        # Get the latest timestamp
        latest_timestamp = db.session.query(db.func.max(WeatherForecast.timestamp)).scalar()
        
        if not latest_timestamp:
            return jsonify({
                'success': False,
                'message': 'No forecast data found'
            }), 404
        
        # Get all forecast items for the latest timestamp
        forecasts = WeatherForecast.query.filter_by(timestamp=latest_timestamp).order_by(WeatherForecast.forecast_dt).all()
        
        if not forecasts:
            return jsonify({
                'success': False,
                'message': 'No forecast data found'
            }), 404
        
        # Group by city and format as forecast response
        city_data = None
        forecast_list = []
        
        for forecast in forecasts:
            if not city_data:
                city_data = forecast.to_dict()['city']
            forecast_list.append({
                'dt': forecast.forecast_dt,
                'dt_txt': forecast.forecast_dt_txt,
                'main': forecast.to_dict()['main'],
                'weather': [forecast.to_dict()['weather']],
                'clouds': forecast.to_dict()['clouds'],
                'wind': forecast.to_dict()['wind'],
                'visibility': forecast.to_dict()['visibility'],
                'pop': forecast.to_dict()['pop'],
                'rain': forecast.to_dict()['rain'],
                'snow': forecast.to_dict()['snow']
            })
        
        return jsonify({
            'success': True,
            'data': {
                'cod': '200',
                'message': 0,
                'cnt': len(forecast_list),
                'list': forecast_list,
                'city': city_data
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error retrieving forecast data: {str(e)}'
        }), 500

# For manual testing of ML prediction staleness check and generation
#check if data is stale and suggest ML prediction
@weather_bp.route('/check-staleness', methods=['GET'])
def check_data_staleness():
    """
    Check if weather data is stale (older than 12 hours).
    Returns staleness status and suggests ML prediction if needed.
    """
    try:
        # Get latest current weather
        latest_current = WeatherCurrent.query.order_by(WeatherCurrent.timestamp.desc()).first()
        
        if not latest_current:
            return jsonify({
                'success': True,
                'is_stale': True,
                'has_data': False,
                'message': 'No weather data found',
                'ml_available': is_ml_available(),
                'suggestion': 'Use ML prediction to generate initial data'
            }), 200
        
        # Check if data is stale
        current_time = datetime.utcnow()
        data_time = datetime.fromtimestamp(latest_current.timestamp / 1000)
        age_hours = (current_time - data_time).total_seconds() / 3600
        
        is_stale = age_hours > 12
        
        return jsonify({
            'success': True,
            'is_stale': is_stale,
            'has_data': True,
            'age_hours': round(age_hours, 2),
            'last_update': latest_current.timestamp,
            'ml_available': is_ml_available(),
            'suggestion': 'Use ML prediction' if is_stale else 'Data is fresh'
        }), 200
        
    except Exception as e:
        logger.error(f"Error checking data staleness: {e}")
        return jsonify({
            'success': False,
            'message': f'Error checking data staleness: {str(e)}'
        }), 500


@weather_bp.route('/predict-ml', methods=['POST'])
def predict_with_ml():
    """
    Generate weather predictions using ML model when API is unavailable.
    Uses last 48 hours of weather_current data to predict next 24 hours.
    """
    try:
        predictor = get_predictor()
        if not predictor:
            return jsonify({
                'success': False,
                'message': 'ML predictor not available. Check model files and dependencies.'
            }), 503
        
        # Get city_id from latest current weather (if available) for filtering
        latest_current = WeatherCurrent.query.order_by(WeatherCurrent.timestamp.desc()).first()
        city_id = latest_current.location_id if latest_current else None
        
        # Build historical data using hybrid approach (current + forecast)
        historical_data, city_info, data_source_info = build_historical_data_for_prediction(
            lookback_hours=predictor.lookback_hours,
            city_id=city_id
        )
        
        if not data_source_info['has_sufficient_data']:
            return jsonify({
                'success': False,
                'message': f'Insufficient historical data. Need at least 48 hours ({predictor.lookback_hours} hours), '
                          f'got {len(historical_data)} records. '
                          f'Sources: {data_source_info["current_count"]} from current, '
                          f'{data_source_info["forecast_count"]} from forecast. '
                          f'This hybrid approach uses both weather_current and weather_forecast tables to handle extended connection loss.'
            }), 400
        
        # Ensure we have exactly the right amount of data
        if len(historical_data) > predictor.lookback_hours:
            historical_data = historical_data[-predictor.lookback_hours:]
        
        # Generate predictions
        predicted_records = predictor.predict(historical_data)
        
        # Get city info from helper function result or fallback to latest current
        if city_info:
            city_id = city_info['id']
            city_name = city_info['name']
            city_country = city_info['country']
            city_coord_lat = city_info['coord_lat']
            city_coord_lon = city_info['coord_lon']
        elif latest_current:
            city_id = latest_current.location_id
            city_name = latest_current.location_name
            city_country = latest_current.country or ''
            city_coord_lat = latest_current.coord_lat
            city_coord_lon = latest_current.coord_lon
        else:
            return jsonify({
                'success': False,
                'message': 'No city information available for predictions'
            }), 400
        
        # Store predictions in both weather_forecast AND weather_current tables
        timestamp = int(datetime.utcnow().timestamp() * 1000)
        forecast_records_created = 0
        current_records_created = 0
        
        # Calculate confidence score based on data sources used
        # API data: 1.0, Real+Forecast: 0.75, With ML predictions: 0.55
        base_confidence = 1.0
        if data_source_info['forecast_count'] > 0:
            base_confidence = 0.75
        if data_source_info.get('ml_prediction_count', 0) > 0:
            base_confidence = 0.55
        
        for pred_record in predicted_records:
            # 1. Store in weather_forecast table
            existing_forecast = WeatherForecast.query.filter_by(
                city_id=city_id,
                forecast_dt=pred_record['forecast_dt']
            ).first()
            
            if existing_forecast:
                # Update existing forecast record
                existing_forecast.timestamp = timestamp
                existing_forecast.synced_at = datetime.utcnow()
                existing_forecast.forecast_dt_txt = pred_record['forecast_dt_txt']
                existing_forecast.temp = pred_record['temp']
                existing_forecast.feels_like = pred_record['feels_like']
                existing_forecast.temp_min = pred_record['temp_min']
                existing_forecast.temp_max = pred_record['temp_max']
                existing_forecast.pressure = pred_record['pressure']
                existing_forecast.humidity = pred_record['humidity']
                existing_forecast.wind_speed = pred_record['wind_speed']
                existing_forecast.wind_deg = pred_record['wind_deg']
                existing_forecast.rain_1h = pred_record.get('rain_1h', 0.0)
                existing_forecast.rain_3h = pred_record.get('rain_3h', 0.0)
                existing_forecast.clouds_all = pred_record.get('clouds_all', 0)
                existing_forecast.weather_main = pred_record.get('weather_main', 'Clear')
                existing_forecast.weather_description = pred_record.get('weather_description', 'clear sky')
                existing_forecast.weather_icon = pred_record.get('weather_icon', '01d')
                existing_forecast.raw_data = json.dumps({
                    **pred_record,
                    'is_ml_prediction': True,
                    'predicted_at': timestamp,
                    'confidence_score': base_confidence
                })
            else:
                # Create new forecast record
                forecast_record = WeatherForecast(
                    timestamp=timestamp,
                    forecast_dt=pred_record['forecast_dt'],
                    forecast_dt_txt=pred_record['forecast_dt_txt'],
                    city_id=city_id,
                    city_name=city_name,
                    city_country=city_country,
                    city_coord_lat=city_coord_lat,
                    city_coord_lon=city_coord_lon,
                    weather_main=pred_record.get('weather_main', 'Clear'),
                    weather_description=pred_record.get('weather_description', 'clear sky'),
                    weather_icon=pred_record.get('weather_icon', '01d'),
                    temp=pred_record['temp'],
                    feels_like=pred_record['feels_like'],
                    temp_min=pred_record['temp_min'],
                    temp_max=pred_record['temp_max'],
                    pressure=pred_record['pressure'],
                    humidity=pred_record['humidity'],
                    wind_speed=pred_record['wind_speed'],
                    wind_deg=pred_record['wind_deg'],
                    rain_1h=pred_record.get('rain_1h', 0.0),
                    rain_3h=pred_record.get('rain_3h', 0.0),
                    clouds_all=pred_record.get('clouds_all', 0),
                    pop=0.0,
                    raw_data=json.dumps({
                        **pred_record,
                        'is_ml_prediction': True,
                        'predicted_at': timestamp,
                        'confidence_score': base_confidence
                    })
                )
                db.session.add(forecast_record)
                forecast_records_created += 1
            
            # 2. Store in weather_current table (enables recursive prediction)
            # This allows future ML predictions to use previous ML predictions as input
            existing_current = WeatherCurrent.query.filter_by(
                location_id=city_id,
                measured_at=pred_record['timestamp']
            ).first()
            
            if not existing_current:
                current_record = WeatherCurrent(
                    timestamp=timestamp,
                    synced_at=datetime.utcnow(),
                    measured_at=pred_record['timestamp'],
                    coord_lon=city_coord_lon,
                    coord_lat=city_coord_lat,
                    location_name=city_name,
                    location_id=city_id,
                    country=city_country,
                    weather_main=pred_record.get('weather_main', 'Clear'),
                    weather_description=pred_record.get('weather_description', 'clear sky'),
                    weather_icon=pred_record.get('weather_icon', '01d'),
                    temp=pred_record['temp'],
                    feels_like=pred_record['feels_like'],
                    temp_min=pred_record['temp_min'],
                    temp_max=pred_record['temp_max'],
                    pressure=pred_record['pressure'],
                    humidity=pred_record['humidity'],
                    wind_speed=pred_record['wind_speed'],
                    wind_deg=pred_record['wind_deg'],
                    rain_1h=pred_record.get('rain_1h', 0.0),
                    rain_3h=pred_record.get('rain_3h', 0.0),
                    clouds_all=pred_record.get('clouds_all', 0),
                    visibility=10000,  # Default visibility
                    # ML tracking fields
                    data_source='ml_prediction',
                    is_ml_generated=True,
                    confidence_score=base_confidence,
                    raw_data=json.dumps({
                        **pred_record,
                        'is_ml_prediction': True,
                        'predicted_at': timestamp,
                        'confidence_score': base_confidence
                    })
                )
                db.session.add(current_record)
                current_records_created += 1
        
        db.session.commit()
        
        logger.info(
            f"✓ ML predictions generated: {len(predicted_records)} predictions (Confidence: {base_confidence:.2f}), "
            f"created {forecast_records_created} forecast records, {current_records_created} current records for recursive prediction. "
            f"Data sources: {data_source_info['current_count']} from current, {data_source_info['forecast_count']} from forecast"
        )
        
        return jsonify({
            'success': True,
            'message': f'Generated {len(predicted_records)} ML predictions',
            'predictions_count': len(predicted_records),
            'forecast_records_created': forecast_records_created,
            'current_records_created': current_records_created,
            'confidence_score': base_confidence,
            'timestamp': timestamp,
            'prediction_intervals': predictor.prediction_intervals,
            'data_sources': {
                'current_count': data_source_info['current_count'],
                'forecast_count': data_source_info['forecast_count'],
                'total_records': len(historical_data)
            }
        }), 200
        
    except ValueError as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 400
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error generating ML predictions: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'message': f'Error generating ML predictions: {str(e)}'
        }), 500


@weather_bp.route('/auto-predict', methods=['POST'])
def auto_predict_if_stale():
    """
    Automatically check if data is stale and generate ML predictions if needed.
    This endpoint should be called periodically when connection is lost.
    """
    try:
        # Check staleness
        latest_current = WeatherCurrent.query.order_by(WeatherCurrent.timestamp.desc()).first()
        
        if not latest_current:
            # No data at all - try to generate predictions if we have historical data
            logger.info("No current weather data, attempting ML prediction...")
            # Will be handled by predict_with_ml logic
        else:
            # Check if data is stale (older than 12 hours)
            current_time = datetime.utcnow()
            data_time = datetime.fromtimestamp(latest_current.timestamp / 1000)
            age_hours = (current_time - data_time).total_seconds() / 3600
            
            if age_hours <= 12:
                return jsonify({
                    'success': True,
                    'action': 'skipped',
                    'message': 'Data is fresh, no prediction needed',
                    'age_hours': round(age_hours, 2)
                }), 200
        
        # Data is stale or missing - generate predictions
        # Call the predict endpoint logic
        predictor = get_predictor()
        if not predictor:
            return jsonify({
                'success': False,
                'action': 'failed',
                'message': 'ML predictor not available'
            }), 503
        
        # Get city_id from latest current weather (if available) for filtering
        latest_current = WeatherCurrent.query.order_by(WeatherCurrent.timestamp.desc()).first()
        city_id = latest_current.location_id if latest_current else None
        
        # Build historical data using hybrid approach (current + forecast)
        historical_data, city_info, data_source_info = build_historical_data_for_prediction(
            lookback_hours=predictor.lookback_hours,
            city_id=city_id
        )
        
        if not data_source_info['has_sufficient_data']:
            return jsonify({
                'success': False,
                'action': 'failed',
                'message': f'Insufficient historical data. Need at least ({predictor.lookback_hours} hours), '
                          f'got {len(historical_data)} records. '
                          f'Sources: {data_source_info["current_count"]} from current, '
                          f'{data_source_info["forecast_count"]} from forecast.'
            }), 400
        
        # Ensure we have exactly the right amount of data
        if len(historical_data) > predictor.lookback_hours:
            historical_data = historical_data[-predictor.lookback_hours:]
        
        # Generate and store predictions
        predicted_records = predictor.predict(historical_data)
        
        # Get city info from helper function result or fallback to latest current
        if city_info:
            city_id = city_info['id']
            city_name = city_info['name']
            city_country = city_info['country']
            city_coord_lat = city_info['coord_lat']
            city_coord_lon = city_info['coord_lon']
        elif latest_current:
            city_id = latest_current.location_id
            city_name = latest_current.location_name
            city_country = latest_current.country or ''
            city_coord_lat = latest_current.coord_lat
            city_coord_lon = latest_current.coord_lon
        else:
            return jsonify({
                'success': False,
                'action': 'failed',
                'message': 'No city information available for predictions'
            }), 400
        
        timestamp = int(datetime.utcnow().timestamp() * 1000)
        forecast_records_created = 0
        current_records_created = 0
        
        # Calculate confidence score based on data sources used
        # API data: 1.0, Real+Forecast: 0.75, With ML predictions: 0.55
        base_confidence = 1.0
        if data_source_info['forecast_count'] > 0:
            base_confidence = 0.75
        if data_source_info.get('ml_prediction_count', 0) > 0:
            base_confidence = 0.55
        
        for pred_record in predicted_records:
            # 1. Store in weather_forecast table
            existing_forecast = WeatherForecast.query.filter_by(
                city_id=city_id,
                forecast_dt=pred_record['forecast_dt']
            ).first()
            
            if existing_forecast:
                # Update existing forecast record
                existing_forecast.timestamp = timestamp
                existing_forecast.synced_at = datetime.utcnow()
                existing_forecast.forecast_dt_txt = pred_record['forecast_dt_txt']
                existing_forecast.temp = pred_record['temp']
                existing_forecast.feels_like = pred_record['feels_like']
                existing_forecast.temp_min = pred_record['temp_min']
                existing_forecast.temp_max = pred_record['temp_max']
                existing_forecast.pressure = pred_record['pressure']
                existing_forecast.humidity = pred_record['humidity']
                existing_forecast.wind_speed = pred_record['wind_speed']
                existing_forecast.wind_deg = pred_record['wind_deg']
                existing_forecast.rain_1h = pred_record.get('rain_1h', 0.0)
                existing_forecast.rain_3h = pred_record.get('rain_3h', 0.0)
                existing_forecast.clouds_all = pred_record.get('clouds_all', 0)
                existing_forecast.weather_main = pred_record.get('weather_main', 'Clear')
                existing_forecast.weather_description = pred_record.get('weather_description', 'clear sky')
                existing_forecast.weather_icon = pred_record.get('weather_icon', '01d')
                existing_forecast.raw_data = json.dumps({
                    **pred_record,
                    'is_ml_prediction': True,
                    'predicted_at': timestamp,
                    'confidence_score': base_confidence
                })
            else:
                # Create new forecast record
                forecast_record = WeatherForecast(
                    timestamp=timestamp,
                    forecast_dt=pred_record['forecast_dt'],
                    forecast_dt_txt=pred_record['forecast_dt_txt'],
                    city_id=city_id,
                    city_name=city_name,
                    city_country=city_country,
                    city_coord_lat=city_coord_lat,
                    city_coord_lon=city_coord_lon,
                    weather_main=pred_record.get('weather_main', 'Clear'),
                    weather_description=pred_record.get('weather_description', 'clear sky'),
                    weather_icon=pred_record.get('weather_icon', '01d'),
                    temp=pred_record['temp'],
                    feels_like=pred_record['feels_like'],
                    temp_min=pred_record['temp_min'],
                    temp_max=pred_record['temp_max'],
                    pressure=pred_record['pressure'],
                    humidity=pred_record['humidity'],
                    wind_speed=pred_record['wind_speed'],
                    wind_deg=pred_record['wind_deg'],
                    rain_1h=pred_record.get('rain_1h', 0.0),
                    rain_3h=pred_record.get('rain_3h', 0.0),
                    clouds_all=pred_record.get('clouds_all', 0),
                    pop=0.0,
                    raw_data=json.dumps({
                        **pred_record,
                        'is_ml_prediction': True,
                        'predicted_at': timestamp,
                        'confidence_score': base_confidence
                    })
                )
                db.session.add(forecast_record)
                forecast_records_created += 1
            
            # 2. Store in weather_current table (enables recursive prediction)
            # This allows future ML predictions to use previous ML predictions as input
            existing_current = WeatherCurrent.query.filter_by(
                location_id=city_id,
                measured_at=pred_record['timestamp']
            ).first()
            
            if not existing_current:
                current_record = WeatherCurrent(
                    timestamp=timestamp,
                    synced_at=datetime.utcnow(),
                    measured_at=pred_record['timestamp'],
                    coord_lon=city_coord_lon,
                    coord_lat=city_coord_lat,
                    location_name=city_name,
                    location_id=city_id,
                    country=city_country,
                    weather_main=pred_record.get('weather_main', 'Clear'),
                    weather_description=pred_record.get('weather_description', 'clear sky'),
                    weather_icon=pred_record.get('weather_icon', '01d'),
                    temp=pred_record['temp'],
                    feels_like=pred_record['feels_like'],
                    temp_min=pred_record['temp_min'],
                    temp_max=pred_record['temp_max'],
                    pressure=pred_record['pressure'],
                    humidity=pred_record['humidity'],
                    wind_speed=pred_record['wind_speed'],
                    wind_deg=pred_record['wind_deg'],
                    rain_1h=pred_record.get('rain_1h', 0.0),
                    rain_3h=pred_record.get('rain_3h', 0.0),
                    clouds_all=pred_record.get('clouds_all', 0),
                    visibility=10000,  # Default visibility
                    # ML tracking fields
                    data_source='ml_prediction',
                    is_ml_generated=True,
                    confidence_score=base_confidence,
                    raw_data=json.dumps({
                        **pred_record,
                        'is_ml_prediction': True,
                        'predicted_at': timestamp,
                        'confidence_score': base_confidence
                    })
                )
                db.session.add(current_record)
                current_records_created += 1
        
        db.session.commit()
        
        logger.info(
            f"✓ Auto-prediction: Generated {len(predicted_records)} predictions (Confidence: {base_confidence:.2f}), "
            f"created {forecast_records_created} forecast records, {current_records_created} current records for recursive prediction. "
            f"Data sources: {data_source_info['current_count']} from current, {data_source_info['forecast_count']} from forecast"
        )
        
        return jsonify({
            'success': True,
            'action': 'predicted',
            'message': f'Generated {len(predicted_records)} ML predictions',
            'predictions_count': len(predicted_records),
            'forecast_records_created': forecast_records_created,
            'current_records_created': current_records_created,
            'confidence_score': base_confidence,
            'timestamp': timestamp,
            'data_sources': {
                'current_count': data_source_info['current_count'],
                'forecast_count': data_source_info['forecast_count'],
                'total_records': len(historical_data)
            }
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in auto-predict: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'action': 'failed',
            'message': f'Error: {str(e)}'
        }), 500

