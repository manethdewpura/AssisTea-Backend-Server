"""Tests for irrigation API and controller."""
import pytest
import time
from app.config.config import ADEQUATE_SOIL_MOISTURE_PERCENT


class TestIrrigationAPI:
    """Test irrigation API endpoints."""
    
    def test_start_irrigation_success(self, client, mock_adc):
        """Test successful irrigation start."""
        # Set soil moisture to low value (needs irrigation)
        # For dry_value=0.833, wet_value=0.344, to get ~30% moisture:
        # normalized = 0.833 - (0.3 * (0.833 - 0.344)) = 0.686
        mock_adc.set_mock_value(1, 0.686)  # Channel 1 for soil moisture
        
        response = client.post('/api/irrigation/start', json={'zone_id': 1})
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['zone_id'] == 1
        assert 'message' in data
    
    def test_start_irrigation_missing_zone_id(self, client):
        """Test irrigation start without zone_id."""
        response = client.post('/api/irrigation/start', json={})
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'zone_id' in data['error'].lower()
    
    def test_start_irrigation_invalid_zone(self, client):
        """Test irrigation start with invalid zone."""
        response = client.post('/api/irrigation/start', json={'zone_id': 999})
        assert response.status_code == 404
        data = response.get_json()
        assert data['success'] is False
    
    def test_start_irrigation_already_running(self, client, mock_adc, irrigation_controller):
        """Test starting irrigation when already running."""
        # Set low moisture
        mock_adc.set_mock_value(1, 0.686)
        
        # Start first irrigation
        response1 = client.post('/api/irrigation/start', json={'zone_id': 1})
        assert response1.status_code == 200
        
        # Try to start another
        response2 = client.post('/api/irrigation/start', json={'zone_id': 2})
        assert response2.status_code == 400
        data = response2.get_json()
        assert data['success'] is False
        assert 'already' in data['message'].lower()
    
    def test_stop_irrigation(self, client, mock_adc):
        """Test stopping irrigation."""
        # Set low moisture and start
        mock_adc.set_mock_value(1, 0.686)
        client.post('/api/irrigation/start', json={'zone_id': 1})
        
        # Stop irrigation
        response = client.post('/api/irrigation/stop')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
    
    def test_stop_irrigation_not_running(self, client):
        """Test stopping irrigation when not running."""
        response = client.post('/api/irrigation/stop')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is False
        assert 'not' in data['message'].lower() or 'no' in data['message'].lower()
    
    def test_get_irrigation_status(self, client):
        """Test getting irrigation status."""
        response = client.get('/api/irrigation/status')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'status' in data
        assert 'is_running' in data['status']
    
    def test_irrigation_skipped_high_moisture(self, client, mock_adc):
        """Test irrigation skipped when moisture is adequate."""
        # Set high moisture (above adequate threshold)
        # For ~70% moisture: normalized = 0.833 - (0.7 * (0.833 - 0.344)) = 0.491
        mock_adc.set_mock_value(1, 0.491)
        
        response = client.post('/api/irrigation/start', json={'zone_id': 1})
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'moisture' in data['message'].lower() or 'adequate' in data['message'].lower()


class TestIrrigationController:
    """Test irrigation controller logic."""
    
    def test_start_irrigation_controller(self, irrigation_controller, mock_adc):
        """Test controller start irrigation."""
        # Set low moisture
        mock_adc.set_mock_value(1, 0.686)
        
        zone_config = {'altitude': 0.0, 'slope': 0.0, 'base_pressure': 200.0}
        result = irrigation_controller.start_irrigation(1, zone_config)
        
        assert result['success'] is True
        assert result['zone_id'] == 1
        assert irrigation_controller.is_running is True
        assert irrigation_controller.current_zone == 1
    
    def test_irrigation_stops_when_adequate_moisture(self, irrigation_controller, mock_adc):
        """Test irrigation stops when adequate moisture is reached."""
        # Start with low moisture
        mock_adc.set_mock_value(1, 0.686)  # ~30%
        
        zone_config = {'altitude': 0.0, 'slope': 0.0, 'base_pressure': 200.0}
        result = irrigation_controller.start_irrigation(1, zone_config)
        assert result['success'] is True
        
        # Simulate moisture increase over time
        # Gradually increase to adequate level
        for i in range(10):
            # Increase moisture gradually: 30% -> 60%
            moisture_normalized = 0.686 - (i * 0.03)
            mock_adc.set_mock_value(1, moisture_normalized)
            time.sleep(0.1)
        
        # Set to adequate level
        # For 60%: normalized = 0.833 - (0.6 * (0.833 - 0.344)) = 0.540
        mock_adc.set_mock_value(1, 0.540)
        
        # Wait for cycle to complete (with timeout)
        timeout = 5
        start = time.time()
        while irrigation_controller.is_running and (time.time() - start) < timeout:
            time.sleep(0.1)
        
        # Should have stopped
        assert irrigation_controller.is_running is False
    
    def test_irrigation_pressure_monitoring(self, irrigation_controller, mock_adc):
        """Test pressure monitoring during irrigation."""
        # Set low moisture
        mock_adc.set_mock_value(1, 0.686)
        
        # Set pressure sensor value
        mock_adc.set_mock_value(0, 0.5)  # Channel 0 for pressure (~250 kPa)
        
        zone_config = {'altitude': 0.0, 'slope': 0.0, 'base_pressure': 200.0}
        result = irrigation_controller.start_irrigation(1, zone_config)
        assert result['success'] is True
        
        # Check that pressure sensor is being read
        status = irrigation_controller.get_status()
        assert 'pump_status' in status
    
    def test_irrigation_weather_check(self, irrigation_controller, mock_adc, mock_weather_reader, tmp_path):
        """Test irrigation blocked by bad weather."""
        import sqlite3
        
        # Create temporary weather DB with rainy condition
        weather_db = tmp_path / 'rainy_weather.db'
        
        conn = sqlite3.connect(str(weather_db))
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS weather (
                timestamp TEXT, condition TEXT, temperature REAL, humidity REAL, precipitation REAL
            )
        ''')
        cursor.execute('''
            INSERT INTO weather VALUES (?, ?, ?, ?, ?)
        ''', ('2024-01-01 12:00:00', 'rainy', 20.0, 80.0, 5.0))
        conn.commit()
        conn.close()
        
        # Update weather reader to use rainy DB
        mock_weather_reader.db_path = str(weather_db)
        
        # Set low moisture
        mock_adc.set_mock_value(1, 0.686)
        
        zone_config = {'altitude': 0.0, 'slope': 0.0, 'base_pressure': 200.0}
        result = irrigation_controller.start_irrigation(1, zone_config)
        
        assert result['success'] is False
        assert 'weather' in result['message'].lower()

