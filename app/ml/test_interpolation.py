"""
Simple manual test script to verify interpolation functionality
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
from app.models.weather_records import (
    db,
    WeatherCurrent,
    WeatherForecast,
    build_historical_data_for_prediction,
    interpolate_weather_data,
)

# Create minimal Flask app
app = Flask(__name__)
basedir = Path(__file__).parent.parent.parent
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{basedir}/database/weather.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

def _validate_hourly(timestamps_ms):
    one_hour_ms = 3600 * 1000
    for i in range(1, len(timestamps_ms)):
        if timestamps_ms[i] - timestamps_ms[i-1] != one_hour_ms:
            return False
    return True


def run_synthetic_interpolation_scenarios():
    from datetime import datetime, timedelta

    print("\n[3] Synthetic interpolation scenarios:")

    # Base time aligned to hour
    base = datetime(2024, 1, 1, 0, 0)
    ms = lambda dt: int(dt.timestamp() * 1000)

    # A) Duplicates within the same hour: keep most recent per bucket
    print("\n  A) Duplicate records within the same hour")
    records = [
        {'timestamp': ms(base + timedelta(hours=0, minutes=15)), 'temp': 20, 'feels_like': 20, 'temp_min': 19, 'temp_max': 21, 'pressure': 1000, 'humidity': 50, 'wind_speed': 2, 'wind_deg': 90, 'rain_1h': 0, 'rain_3h': 0},
        {'timestamp': ms(base + timedelta(hours=0, minutes=45)), 'temp': 21, 'feels_like': 21, 'temp_min': 20, 'temp_max': 22, 'pressure': 1001, 'humidity': 51, 'wind_speed': 2.5, 'wind_deg': 100, 'rain_1h': 0, 'rain_3h': 0},
        {'timestamp': ms(base + timedelta(hours=1)), 'temp': 22, 'feels_like': 22, 'temp_min': 21, 'temp_max': 23, 'pressure': 1002, 'humidity': 52, 'wind_speed': 3, 'wind_deg': 110, 'rain_1h': 0, 'rain_3h': 0},
    ]
    out, count = interpolate_weather_data(records, lookback_hours=2)
    print(f"    - Output len={len(out)}, interpolated={count}")
    print(f"    - First hour temp should be from latest within hour (21): {out[0]['temp']}")

    # B) Large gaps: ensure interpolation fills to exact window
    print("\n  B) Gapped records over long span")
    sparse = []
    for h in [0, 10, 25, 47, 80]:
        sparse.append({'timestamp': ms(base + timedelta(hours=h)), 'temp': 15 + h*0.1, 'feels_like': 15 + h*0.1,
                       'temp_min': 14 + h*0.1, 'temp_max': 16 + h*0.1, 'pressure': 1000, 'humidity': 60,
                       'wind_speed': 2, 'wind_deg': 180, 'rain_1h': 0, 'rain_3h': 0})
    out, count = interpolate_weather_data(sparse, lookback_hours=48)
    ts = [r['timestamp'] for r in out]
    print(f"    - Output len={len(out)}, interpolated={count}")
    print(f"    - Continuous hourly: {_validate_hourly(ts)}")
    print(f"    - Oldest ts: {datetime.fromtimestamp(ts[0]/1000)} | Newest ts: {datetime.fromtimestamp(ts[-1]/1000)}")

    # C) Insufficient span (forces extrapolation warning & forward-fill end)
    print("\n  C) Insufficient timespan; extrapolation beyond latest data")
    short = []
    for h in range(0, 6):
        short.append({'timestamp': ms(base + timedelta(hours=h)), 'temp': 10 + h, 'feels_like': 10 + h,
                      'temp_min': 9 + h, 'temp_max': 11 + h, 'pressure': 1000, 'humidity': 55,
                      'wind_speed': 1.5, 'wind_deg': 200, 'rain_1h': 0, 'rain_3h': 0})
    out, count = interpolate_weather_data(short, lookback_hours=12)
    ts = [r['timestamp'] for r in out]
    print(f"    - Output len={len(out)}, interpolated={count}")
    print(f"    - Continuous hourly: {_validate_hourly(ts)}")


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

    # Run synthetic checks to validate interpolation changes
    run_synthetic_interpolation_scenarios()
    
    print("\n" + "="*70)
    print("TEST COMPLETE")
    print("="*70 + "\n")
