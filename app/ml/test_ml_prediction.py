"""
Test script for ML prediction system with new features:
- Dual storage (weather_forecast + weather_current)
- Confidence scoring
- Recursive prediction capability
"""

import sys
import os
from pathlib import Path

# Add project root to path so we can import from app module
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

from flask import Flask
from app.models.weather_records import db, WeatherCurrent, WeatherForecast, build_historical_data_for_prediction
from app.ml.predictor import get_predictor, is_ml_available
from datetime import datetime, timedelta
import json

def test_ml_prediction_system(app):
    """Test the ML prediction system"""
    
    with app.app_context():
        print("\n" + "="*70)
        print("ML PREDICTION SYSTEM TEST")
        print("="*70)
        
        # Test 1: Check ML Availability
        print("\n[Test 1] Checking ML Model Availability...")
        if is_ml_available():
            print("✓ ML predictor is available")
            predictor = get_predictor()
            print(f"  - Lookback hours: {predictor.lookback_hours}")
            print(f"  - Prediction intervals: {predictor.prediction_intervals}")
        else:
            print("✗ ML predictor is NOT available")
            return
        
        # Test 2: Check Current Data State
        print("\n[Test 2] Current Database State...")
        current_count = WeatherCurrent.query.count()
        forecast_count = WeatherForecast.query.count()
        ml_generated_count = WeatherCurrent.query.filter_by(is_ml_generated=True).count()
        
        print(f"  - weather_current: {current_count} records")
        print(f"    └─ ML-generated: {ml_generated_count} records")
        print(f"  - weather_forecast: {forecast_count} records")
        
        # Test 3: Build Historical Data
        print("\n[Test 3] Building Historical Data for Prediction...")
        try:
            historical_data, city_info, data_source_info = build_historical_data_for_prediction(
                lookback_hours=predictor.lookback_hours
            )
            
            print(f"  - Total records retrieved: {len(historical_data)}")
            print(f"  - From weather_current: {data_source_info['current_count']}")
            print(f"  - From weather_forecast: {data_source_info['forecast_count']}")
            print(f"  - From ML predictions: {data_source_info.get('ml_prediction_count', 0)}")
            print(f"  - Sufficient data: {data_source_info['has_sufficient_data']}")
            
            if city_info:
                print(f"  - City: {city_info['name']}, {city_info['country']}")
            
            if not data_source_info['has_sufficient_data']:
                print(f"\n⚠ WARNING: Insufficient data for prediction (need at least 48 records)")
                print(f"  Current records: {len(historical_data)}")
                print(f"\nℹ This is expected for a new database. Options:")
                print(f"  1. Wait for API to collect more data (48 hours worth)")
                print(f"  2. Use weather_forecast data (already available)")
                print(f"\nThe system will use available forecast data to supplement.")
        
        except Exception as e:
            print(f"✗ Error building historical data: {e}")
            import traceback
            traceback.print_exc()
            return
        
        # Test 4: Generate ML Predictions
        print("\n[Test 4] Generating ML Predictions...")
        
        if len(historical_data) < 48:
            print(f"⚠ Only {len(historical_data)} records available, need at least 48")
            print("  Attempting prediction anyway (may use forecast data)...")
        
        try:
            # Calculate confidence based on data sources
            base_confidence = 1.0
            if data_source_info['forecast_count'] > 0:
                base_confidence = 0.75
            if data_source_info.get('ml_prediction_count', 0) > 0:
                base_confidence = 0.55
            
            print(f"  - Predicted confidence score: {base_confidence:.2f}")
            
            predicted_records = predictor.predict(historical_data)
            print(f"✓ Generated {len(predicted_records)} predictions")
            
            # Show first prediction
            if predicted_records:
                first_pred = predicted_records[0]
                print(f"\n  First Prediction:")
                print(f"    - Time: {first_pred['forecast_dt_txt']}")
                print(f"    - Temperature: {first_pred['temp']:.1f}°C")
                print(f"    - Humidity: {first_pred['humidity']:.0f}%")
                print(f"    - Weather: {first_pred['weather_description']}")
                print(f"    - Rain (1h): {first_pred['rain_1h']:.2f}mm")
        
        except Exception as e:
            print(f"✗ Error generating predictions: {e}")
            import traceback
            traceback.print_exc()
            return
        
        # Test 5: Store Predictions (Dual Storage)
        print("\n[Test 5] Testing Dual Storage (forecast + current tables)...")
        
        try:
            timestamp = int(datetime.utcnow().timestamp() * 1000)
            forecast_created = 0
            current_created = 0
            
            if not city_info:
                print("✗ No city information available")
                return
            
            city_id = city_info['id']
            city_name = city_info['name']
            city_country = city_info['country']
            city_coord_lat = city_info['coord_lat']
            city_coord_lon = city_info['coord_lon']
            
            for pred_record in predicted_records:
                # Store in weather_forecast
                existing_forecast = WeatherForecast.query.filter_by(
                    city_id=city_id,
                    forecast_dt=pred_record['forecast_dt']
                ).first()
                
                if not existing_forecast:
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
                    forecast_created += 1
                
                # Store in weather_current (NEW - for recursive prediction)
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
                        visibility=10000,
                        # ML tracking fields (NEW)
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
                    current_created += 1
            
            db.session.commit()
            print(f"✓ Dual storage successful:")
            print(f"  - weather_forecast: {forecast_created} new records")
            print(f"  - weather_current: {current_created} new records (for recursive prediction)")
        
        except Exception as e:
            db.session.rollback()
            print(f"✗ Error storing predictions: {e}")
            import traceback
            traceback.print_exc()
            return
        
        # Test 6: Verify Storage
        print("\n[Test 6] Verifying Storage...")
        
        new_current_count = WeatherCurrent.query.count()
        new_forecast_count = WeatherForecast.query.count()
        new_ml_count = WeatherCurrent.query.filter_by(is_ml_generated=True).count()
        
        print(f"  - weather_current: {current_count} → {new_current_count} (+{new_current_count - current_count})")
        print(f"  - weather_forecast: {forecast_count} → {new_forecast_count} (+{new_forecast_count - forecast_count})")
        print(f"  - ML-generated in current: {ml_generated_count} → {new_ml_count} (+{new_ml_count - ml_generated_count})")
        
        # Show ML-generated records
        if new_ml_count > 0:
            print(f"\n  ML-Generated Records in weather_current:")
            ml_records = WeatherCurrent.query.filter_by(is_ml_generated=True).order_by(WeatherCurrent.measured_at.asc()).limit(3).all()
            for i, record in enumerate(ml_records, 1):
                dt = datetime.fromtimestamp(record.measured_at / 1000)
                print(f"    {i}. {dt.strftime('%Y-%m-%d %H:%M')} - {record.temp:.1f}°C - "
                      f"Source: {record.data_source} - Confidence: {record.confidence_score:.2f}")
        
        # Test 7: Test Recursive Prediction Capability
        print("\n[Test 7] Testing Recursive Prediction Capability...")
        print("  (Attempting to use ML predictions as input for new predictions)")
        
        try:
            historical_data_v2, city_info_v2, data_source_info_v2 = build_historical_data_for_prediction(
                lookback_hours=predictor.lookback_hours
            )
            
            print(f"  - Total records: {len(historical_data_v2)}")
            print(f"  - From weather_current (real): {data_source_info_v2['current_count'] - data_source_info_v2.get('ml_prediction_count', 0)}")
            print(f"  - From weather_forecast: {data_source_info_v2['forecast_count']}")
            print(f"  - From ML predictions: {data_source_info_v2.get('ml_prediction_count', 0)}")
            
            if data_source_info_v2.get('ml_prediction_count', 0) > 0:
                print(f"✓ Recursive prediction capability CONFIRMED!")
                print(f"  System is now able to use previous ML predictions as input")
            else:
                print(f"  No ML predictions used yet (this is normal after first run)")
                print(f"  Recursive capability will activate when more predictions accumulate")
        
        except Exception as e:
            print(f"✗ Error testing recursive capability: {e}")
            import traceback
            traceback.print_exc()
        
        print("\n" + "="*70)
        print("TEST COMPLETE")
        print("="*70)
        print("\nSummary:")
        print(f"  ✓ ML model loaded and functional")
        print(f"  ✓ Predictions generated: {len(predicted_records)}")
        print(f"  ✓ Dual storage working (forecast + current tables)")
        print(f"  ✓ Confidence tracking: {base_confidence:.2f}")
        print(f"  ✓ Data source tracking: {data_source_info}")
        
        if new_ml_count > 0:
            print(f"  ✓ Recursive prediction capability: READY")
        else:
            print(f"  ⏳ Recursive capability: Pending (needs more data)")
        
        print("\n")


if __name__ == '__main__':
    # Import your Flask app
    try:
        from main import app
    except ImportError:
        print("Error: Could not import 'app' from main.py")
        print("Make sure the project structure is correct")
        sys.exit(1)
    
    test_ml_prediction_system(app)
