"""
Simple test script to verify interpolation functionality
Tests the build_historical_data_for_prediction function with current database
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

import os
os.environ['FLASK_APP'] = 'main'

from flask import Flask
from app.models.weather_records import db, WeatherCurrent, WeatherForecast, build_historical_data_for_prediction

# Create minimal Flask app
app = Flask(__name__)
basedir = Path(__file__).parent.parent.parent
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{basedir}/database/weather.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

with app.app_context():
    db.init_app(app)
    
    print("\n" + "="*70)
    print("INTERPOLATION TEST")
    print("="*70)
    
    # Check database state
    print("\n[1] Current Database State:")
    current_count = WeatherCurrent.query.count()
    forecast_count = WeatherForecast.query.count()
    print(f"  - weather_current: {current_count} records")
    print(f"  - weather_forecast: {forecast_count} records")
    print(f"  - Total: {current_count + forecast_count} records")
    
    # Test historical data building with interpolation
    print("\n[2] Building Historical Data (48 hours required):")
    try:
        historical_data, city_info, data_source_info = build_historical_data_for_prediction(
            lookback_hours=48
        )
        
        print(f"\n  Results:")
        print(f"  - Total records retrieved: {len(historical_data)}")
        print(f"  - From weather_current: {data_source_info['current_count']}")
        print(f"  - From weather_forecast: {data_source_info['forecast_count']}")
        print(f"  - Interpolated records: {data_source_info.get('interpolated_count', 0)}")
        print(f"  - Interpolation ratio: {data_source_info.get('interpolation_ratio', 0):.1%}")
        print(f"  - Data quality: {data_source_info.get('data_quality', 'unknown')}")
        print(f"  - Sufficient data: {data_source_info['has_sufficient_data']}")
        
        if city_info:
            print(f"\n  Location: {city_info['name']}, {city_info['country']}")
        
        if data_source_info['has_sufficient_data']:
            print(f"\n✓ SUCCESS: ML Prediction can now proceed!")
            print(f"  Confidence adjustment: ~{(1 - data_source_info.get('interpolation_ratio', 0) * 0.3):.2%}")
        else:
            print(f"\n✗ FAILED: Still insufficient data")
            
        # Show sample of data timeline
        if len(historical_data) > 0:
            print(f"\n  Sample timeline (first 5 and last 5 records):")
            from datetime import datetime
            for i, record in enumerate(historical_data[:5] + historical_data[-5:]):
                if i == 5:
                    print("  ...")
                dt = datetime.fromtimestamp(record['timestamp'] / 1000)
                print(f"    {dt.strftime('%Y-%m-%d %H:%M')} - Temp: {record['temp']:.1f}°C")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*70)
    print("TEST COMPLETE")
    print("="*70 + "\n")
