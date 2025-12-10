from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
from database import db, WeatherCurrent, WeatherForecast
from sqlalchemy.exc import IntegrityError
import json

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
    """Sync current weather data to database (keeps only latest record)"""
    try:
        data = request.json
        
        if not data or 'data' not in data:
            return jsonify({
                'success': False,
                'message': 'Invalid request: missing data field'
            }), 400
        
        weather_data = data['data']
        timestamp = data.get('timestamp', int(datetime.utcnow().timestamp() * 1000))
        
        # Extract weather condition
        weather_condition = extract_weather_data(weather_data.get('weather', []))
        
        # Delete old current weather records (we only need the latest)
        location_id = weather_data.get('id')
        if location_id:
            WeatherCurrent.query.filter_by(location_id=location_id).delete()
        else:
            # If no location_id, delete all (fallback)
            WeatherCurrent.query.delete()
        
        # Create new current weather record
        weather_record = WeatherCurrent(
            timestamp=timestamp,
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
            sea_level=weather_data.get('main', {}).get('sea_level'),
            grnd_level=weather_data.get('main', {}).get('grnd_level'),
            wind_speed=weather_data.get('wind', {}).get('speed'),
            wind_deg=weather_data.get('wind', {}).get('deg'),
            wind_gust=weather_data.get('wind', {}).get('gust'),
            visibility=weather_data.get('visibility'),
            clouds_all=weather_data.get('clouds', {}).get('all'),
            rain_1h=weather_data.get('rain', {}).get('1h') if weather_data.get('rain') else None,
            rain_3h=weather_data.get('rain', {}).get('3h') if weather_data.get('rain') else None,
            snow_1h=weather_data.get('snow', {}).get('1h') if weather_data.get('snow') else None,
            snow_3h=weather_data.get('snow', {}).get('3h') if weather_data.get('snow') else None,
            country=weather_data.get('sys', {}).get('country', ''),
            sunrise=weather_data.get('sys', {}).get('sunrise'),
            sunset=weather_data.get('sys', {}).get('sunset'),
            raw_data=json.dumps(weather_data)
        )
        
        db.session.add(weather_record)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Current weather data synced (old records replaced)',
            'syncedAt': int(datetime.utcnow().timestamp() * 1000),
            'recordId': weather_record.id
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': 'An error occurred while syncing current weather data'
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
        
        # Batch-load all existing forecasts for this city
        city_id = city_data.get('id')
        
        existing_forecasts = {
            f.forecast_dt: f 
            for f in WeatherForecast.query.filter_by(city_id=city_id).all()
        }
        
        # Store each forecast item with UPSERT logic
        for item in forecast_list:
            weather_condition = extract_weather_data(item.get('weather', []))
            
            forecast_dt = item.get('dt')
            
            # Use dictionary lookup instead of querying in the loop
            existing = existing_forecasts.get(forecast_dt)
            
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
                existing.city_sunrise = city_data.get('sunrise')
                existing.city_sunset = city_data.get('sunset')
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
                existing.sea_level = item.get('main', {}).get('sea_level')
                existing.grnd_level = item.get('main', {}).get('grnd_level')
                existing.wind_speed = item.get('wind', {}).get('speed')
                existing.wind_deg = item.get('wind', {}).get('deg')
                existing.wind_gust = item.get('wind', {}).get('gust')
                existing.visibility = item.get('visibility')
                existing.clouds_all = item.get('clouds', {}).get('all')
                existing.pop = item.get('pop', 0)
                existing.rain_1h = item.get('rain', {}).get('1h') if item.get('rain') else None
                existing.rain_3h = item.get('rain', {}).get('3h') if item.get('rain') else None
                existing.snow_1h = item.get('snow', {}).get('1h') if item.get('snow') else None
                existing.snow_3h = item.get('snow', {}).get('3h') if item.get('snow') else None
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
                    city_sunrise=city_data.get('sunrise'),
                    city_sunset=city_data.get('sunset'),
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
                    sea_level=item.get('main', {}).get('sea_level'),
                    grnd_level=item.get('main', {}).get('grnd_level'),
                    wind_speed=item.get('wind', {}).get('speed'),
                    wind_deg=item.get('wind', {}).get('deg'),
                    wind_gust=item.get('wind', {}).get('gust'),
                    visibility=item.get('visibility'),
                    clouds_all=item.get('clouds', {}).get('all'),
                    pop=item.get('pop', 0),
                    rain_1h=item.get('rain', {}).get('1h') if item.get('rain') else None,
                    rain_3h=item.get('rain', {}).get('3h') if item.get('rain') else None,
                    snow_1h=item.get('snow', {}).get('1h') if item.get('snow') else None,
                    snow_3h=item.get('snow', {}).get('3h') if item.get('snow') else None,
                    raw_data=json.dumps(item)
                )
                
                db.session.add(forecast_record)
                records_created += 1
        
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            # Handle race condition: another request may have inserted the same forecast
            current_app.logger.warning('Duplicate forecast detected during commit, handling gracefully')
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
        return jsonify({
            'success': False,
            'message': 'An error occurred while syncing forecast data'
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
        current_data = data.get('current')
        forecast_data = data.get('forecast')
        
        results = {
            'current': None,
            'forecast': None
        }
        
        # Sync current weather if provided
        if current_data:
            weather_condition = extract_weather_data(current_data.get('weather', []))
            
            # Delete old current weather records (we only need the latest)
            location_id = current_data.get('id')
            if location_id:
                WeatherCurrent.query.filter_by(location_id=location_id).delete()
            else:
                WeatherCurrent.query.delete()
            
            weather_record = WeatherCurrent(
                timestamp=timestamp,
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
                sea_level=current_data.get('main', {}).get('sea_level'),
                grnd_level=current_data.get('main', {}).get('grnd_level'),
                wind_speed=current_data.get('wind', {}).get('speed'),
                wind_deg=current_data.get('wind', {}).get('deg'),
                wind_gust=current_data.get('wind', {}).get('gust'),
                visibility=current_data.get('visibility'),
                clouds_all=current_data.get('clouds', {}).get('all'),
                rain_1h=current_data.get('rain', {}).get('1h') if current_data.get('rain') else None,
                rain_3h=current_data.get('rain', {}).get('3h') if current_data.get('rain') else None,
                snow_1h=current_data.get('snow', {}).get('1h') if current_data.get('snow') else None,
                snow_3h=current_data.get('snow', {}).get('3h') if current_data.get('snow') else None,
                country=current_data.get('sys', {}).get('country', ''),
                sunrise=current_data.get('sys', {}).get('sunrise'),
                sunset=current_data.get('sys', {}).get('sunset'),
                raw_data=json.dumps(current_data)
            )
            
            db.session.add(weather_record)
            results['current'] = {'id': weather_record.id, 'success': True}
        
        # Sync forecast if provided
        if forecast_data:
            city_data = forecast_data.get('city', {})
            forecast_list = forecast_data.get('list', [])
            
            forecast_created = 0
            forecast_updated = 0
            
            city_id = city_data.get('id')
            
            # Batch-load all existing forecasts for this city
            existing_forecasts = {
                f.forecast_dt: f 
                for f in WeatherForecast.query.filter_by(city_id=city_id).all()
            }
            
            for item in forecast_list:
                weather_condition = extract_weather_data(item.get('weather', []))
                
                forecast_dt = item.get('dt')
                
                # Use dictionary lookup instead of querying in the loop
                existing = existing_forecasts.get(forecast_dt)
                
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
                    existing.city_sunrise = city_data.get('sunrise')
                    existing.city_sunset = city_data.get('sunset')
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
                    existing.sea_level = item.get('main', {}).get('sea_level')
                    existing.grnd_level = item.get('main', {}).get('grnd_level')
                    existing.wind_speed = item.get('wind', {}).get('speed')
                    existing.wind_deg = item.get('wind', {}).get('deg')
                    existing.wind_gust = item.get('wind', {}).get('gust')
                    existing.visibility = item.get('visibility')
                    existing.clouds_all = item.get('clouds', {}).get('all')
                    existing.pop = item.get('pop', 0)
                    existing.rain_1h = item.get('rain', {}).get('1h') if item.get('rain') else None
                    existing.rain_3h = item.get('rain', {}).get('3h') if item.get('rain') else None
                    existing.snow_1h = item.get('snow', {}).get('1h') if item.get('snow') else None
                    existing.snow_3h = item.get('snow', {}).get('3h') if item.get('snow') else None
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
                        city_sunrise=city_data.get('sunrise'),
                        city_sunset=city_data.get('sunset'),
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
                        sea_level=item.get('main', {}).get('sea_level'),
                        grnd_level=item.get('main', {}).get('grnd_level'),
                        wind_speed=item.get('wind', {}).get('speed'),
                        wind_deg=item.get('wind', {}).get('deg'),
                        wind_gust=item.get('wind', {}).get('gust'),
                        visibility=item.get('visibility'),
                        clouds_all=item.get('clouds', {}).get('all'),
                        pop=item.get('pop', 0),
                        rain_1h=item.get('rain', {}).get('1h') if item.get('rain') else None,
                        rain_3h=item.get('rain', {}).get('3h') if item.get('rain') else None,
                        snow_1h=item.get('snow', {}).get('1h') if item.get('snow') else None,
                        snow_3h=item.get('snow', {}).get('3h') if item.get('snow') else None,
                        raw_data=json.dumps(item)
                    )
                    
                    db.session.add(forecast_record)
                    forecast_created += 1
            
            results['forecast'] = {
                'created': forecast_created,
                'updated': forecast_updated,
                'success': True
            }
        
        # Only commit if there's actual data to sync
        if current_data or forecast_data:
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                # Handle race condition: another request may have inserted the same forecast
                current_app.logger.warning('Duplicate forecast detected during sync commit, handling gracefully')
                db.session.commit()
            return jsonify({
                'success': True,
                'message': 'Weather data synced successfully',
                'syncedAt': int(datetime.utcnow().timestamp() * 1000),
                'results': results
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': 'No data provided to sync'
            }), 400
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': 'An error occurred while syncing weather data'
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
            'message': 'An error occurred while retrieving weather data'
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
            forecast_dict = forecast.to_dict()
            if not city_data:
                city_data = forecast_dict['city']
            forecast_list.append({
                'dt': forecast.forecast_dt,
                'dt_txt': forecast.forecast_dt_txt,
                'main': forecast_dict['main'],
                'weather': [forecast_dict['weather']],
                'clouds': forecast_dict['clouds'],
                'wind': forecast_dict['wind'],
                'visibility': forecast_dict['visibility'],
                'pop': forecast_dict['pop'],
                'rain': forecast_dict['rain'],
                'snow': forecast_dict['snow']
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
            'message': 'An error occurred while retrieving forecast data'
        }), 500

