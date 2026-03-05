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

        # Force decision engine to allow irrigation regardless of exact moisture reading
        from app.api import irrigation as irrigation_api
        irrigation_ctrl = irrigation_api.controllers['irrigation']
        original_decision = irrigation_ctrl.decision_engine.should_irrigate

        def always_irrigate(moisture, weather):
            return {
                'should_irrigate': True,
                'reason': 'test-allow',
                'user_message': 'ok',
                'confidence': 1.0,
            }

        irrigation_ctrl.decision_engine.should_irrigate = always_irrigate
        response = client.post('/api/irrigation/start', json={'zone_id': 1})
        irrigation_ctrl.decision_engine.should_irrigate = original_decision
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

        # Force decision engine to allow irrigation
        from app.api import irrigation as irrigation_api
        irrigation_ctrl = irrigation_api.controllers['irrigation']
        original_decision = irrigation_ctrl.decision_engine.should_irrigate

        def always_irrigate(moisture, weather):
            return {
                'should_irrigate': True,
                'reason': 'test-allow',
                'user_message': 'ok',
                'confidence': 1.0,
            }

        irrigation_ctrl.decision_engine.should_irrigate = always_irrigate
        try:
            # Start first irrigation for the valid zone
            response1 = client.post('/api/irrigation/start', json={'zone_id': 1})
            assert response1.status_code == 200

            # Try to start another for the same zone while it's already running
            response2 = client.post('/api/irrigation/start', json={'zone_id': 1})
            assert response2.status_code == 400
            data = response2.get_json()
            assert data['success'] is False
            assert 'already' in data['message'].lower()
        finally:
            irrigation_ctrl.decision_engine.should_irrigate = original_decision
    
    def test_stop_irrigation(self, client, mock_adc):
        """Test stopping irrigation."""
        # Set low moisture and start
        mock_adc.set_mock_value(1, 0.686)

        # Ensure irrigation can start successfully
        from app.api import irrigation as irrigation_api
        irrigation_ctrl = irrigation_api.controllers['irrigation']
        original_decision = irrigation_ctrl.decision_engine.should_irrigate

        def always_irrigate(moisture, weather):
            return {
                'should_irrigate': True,
                'reason': 'test-allow',
                'user_message': 'ok',
                'confidence': 1.0,
            }

        irrigation_ctrl.decision_engine.should_irrigate = always_irrigate
        client.post('/api/irrigation/start', json={'zone_id': 1})
        irrigation_ctrl.decision_engine.should_irrigate = original_decision
        
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
    
    def test_start_irrigation_non_dict_payload(self, client):
        """Test irrigation start with non-dict JSON payload."""
        response = client.post('/api/irrigation/start', json=['not', 'a', 'dict'])
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'invalid json payload' in data['error'].lower()
        assert 'request body must be a json object' in data['message'].lower()
    
    def test_start_irrigation_controller_not_initialized(self, client, monkeypatch):
        """Test irrigation start when controller is not initialized."""
        from app.api import irrigation as irrigation_api
        
        original_controllers = dict(irrigation_api.controllers)
        try:
            irrigation_api.controllers = {}
            response = client.post('/api/irrigation/start', json={'zone_id': 1})
            assert response.status_code == 500
            data = response.get_json()
            assert data['success'] is False
            assert 'controller not initialized' in data['error'].lower()
        finally:
            irrigation_api.controllers = original_controllers
    
    def test_start_irrigation_serialization_error_handled(self, client, monkeypatch):
        """Test irrigation start handles JSON serialization errors gracefully."""
        from app.api import irrigation as irrigation_api
        
        class BadController:
            def start_irrigation(self, zone_id, zone_config):
                # Return a non-JSON-serializable object
                return {
                    'success': True,
                    'zone_id': zone_id,
                    'bad_field': set([1, 2, 3]),
                }
        
        original_controllers = dict(irrigation_api.controllers)
        try:
            irrigation_api.controllers = {'irrigation': BadController()}
            response = client.post('/api/irrigation/start', json={'zone_id': 1})
            assert response.status_code == 500
            data = response.get_json()
            assert data['success'] is False
            assert 'data serialization failed' in data['error'].lower()
        finally:
            irrigation_api.controllers = original_controllers


class TestIrrigationController:
    """Test irrigation controller logic."""
    
    def test_start_irrigation_controller(self, irrigation_controller, mock_adc):
        """Test controller start irrigation."""
        # Set low moisture
        mock_adc.set_mock_value(1, 0.686)

        # Force decision engine to allow irrigation regardless of exact moisture reading
        original_decision = irrigation_controller.decision_engine.should_irrigate

        def always_irrigate(moisture, weather):
            return {
                'should_irrigate': True,
                'reason': 'test-allow',
                'user_message': 'ok',
                'confidence': 1.0,
            }

        irrigation_controller.decision_engine.should_irrigate = always_irrigate
        zone_config = {'slope': 0.0, 'base_pressure': 200.0}
        result = irrigation_controller.start_irrigation(1, zone_config)
        
        assert result['success'] is True
        assert result['zone_id'] == 1
        assert irrigation_controller.is_running is True
        assert irrigation_controller.current_zone == 1

        irrigation_controller.decision_engine.should_irrigate = original_decision
    
    def test_irrigation_stops_when_adequate_moisture(self, irrigation_controller, mock_adc, monkeypatch):
        """Test irrigation stops when adequate moisture is reached."""
        # Start with low moisture
        mock_adc.set_mock_value(1, 0.686)  # ~30%

        original_decision = irrigation_controller.decision_engine.should_irrigate

        def always_irrigate(moisture, weather):
            return {
                'should_irrigate': True,
                'reason': 'test-allow',
                'user_message': 'ok',
                'confidence': 1.0,
            }

        irrigation_controller.decision_engine.should_irrigate = always_irrigate

        # Make the soil moisture sensor always report adequate moisture inside the cycle
        from app.config.config import ADEQUATE_SOIL_MOISTURE_PERCENT
        def always_wet():
            return {
                'value': ADEQUATE_SOIL_MOISTURE_PERCENT + 5.0,
                'unit': '%',
                'raw_value': 0.5,
                'raw_unit': 'raw',
                'timestamp': None,
                'sensor_id': 'test',
                'zone_id': 1,
            }
        irrigation_controller.soil_moisture_sensors[1].read_standardized = always_wet

        # Speed up loop timing in the controller module
        import app.controllers.irrigation_controller as ic_mod
        monkeypatch.setattr(ic_mod, 'MOISTURE_CHECK_INTERVAL_SEC', 0.1, raising=False)
        monkeypatch.setattr(ic_mod, 'MAX_OPERATION_DURATION_SEC', 5, raising=False)
        zone_config = {'slope': 0.0, 'base_pressure': 200.0}
        result = irrigation_controller.start_irrigation(1, zone_config)
        assert result['success'] is True
        
        # Wait for cycle to complete (with timeout)
        timeout = 5
        start = time.time()
        while irrigation_controller.is_running and (time.time() - start) < timeout:
            time.sleep(0.1)
        
        # Should have stopped
        assert irrigation_controller.is_running is False

        irrigation_controller.decision_engine.should_irrigate = original_decision
    
    def test_irrigation_pressure_monitoring(self, irrigation_controller, mock_adc):
        """Test pressure monitoring during irrigation."""
        # Set low moisture
        mock_adc.set_mock_value(1, 0.686)

        original_decision = irrigation_controller.decision_engine.should_irrigate

        def always_irrigate(moisture, weather):
            return {
                'should_irrigate': True,
                'reason': 'test-allow',
                'user_message': 'ok',
                'confidence': 1.0,
            }

        irrigation_controller.decision_engine.should_irrigate = always_irrigate
        # Set pressure sensor value
        mock_adc.set_mock_value(0, 0.5)  # Channel 0 for pressure (~250 kPa)
        
        zone_config = {'slope': 0.0, 'base_pressure': 200.0}
        result = irrigation_controller.start_irrigation(1, zone_config)
        assert result['success'] is True
        
        # Check that pressure sensor is being read
        status = irrigation_controller.get_status()
        assert 'pump_status' in status

        irrigation_controller.decision_engine.should_irrigate = original_decision
    
    def test_get_irrigation_status_weather_error(self, irrigation_controller, monkeypatch):
        """Test get_status handles weather reader errors gracefully."""
        def bad_weather():
            raise Exception('weather db down')
        irrigation_controller.weather_reader.read_standardized = bad_weather

        status = irrigation_controller.get_status()
        assert 'weather' in status
        assert 'error' in status['weather']
    
    def test_start_irrigation_weather_read_failure(self, irrigation_controller, mock_adc, monkeypatch):
        """Test controller handles weather reader failure."""
        # Force weather reader to raise
        def boom():
            raise Exception('boom')
        irrigation_controller.weather_reader.read_standardized = boom
        
        mock_adc.set_mock_value(1, 0.686)
        zone_config = {'slope': 0.0, 'base_pressure': 200.0}
        result = irrigation_controller.start_irrigation(1, zone_config)
        
        assert result['success'] is False
        assert result.get('error') == 'weather_read_failed'
        assert 'failed to retrieve weather data' in result['message'].lower()

    def test_start_irrigation_non_clear_weather_simple(self, irrigation_controller, mock_adc, monkeypatch):
        """Test controller skips irrigation on non-clear weather without DB access."""
        def rainy():
            return {
                'condition': 'rainy',
                'temperature': 20.0,
                'humidity': 80.0,
                'precipitation': 5.0,
            }
        irrigation_controller.weather_reader.read_standardized = rainy
        
        mock_adc.set_mock_value(1, 0.686)
        zone_config = {'slope': 0.0, 'base_pressure': 200.0}
        result = irrigation_controller.start_irrigation(1, zone_config)
        
        assert result['success'] is False
        assert 'weather is rainy' in result['message'].lower()

    def test_start_irrigation_missing_soil_moisture_sensor(self, irrigation_controller, mock_adc):
        """Test controller path when soil moisture sensor is missing for zone."""
        zone_config = {'slope': 0.0, 'base_pressure': 200.0}
        result = irrigation_controller.start_irrigation(999, zone_config)
        assert result['success'] is False
        assert 'no soil moisture sensor configured' in result['message'].lower()

    def test_irrigation_timeout_path(self, irrigation_controller, mock_adc, monkeypatch):
        """Test irrigation loop exits via MAX_OPERATION_DURATION_SEC timeout."""
        # Make moisture stay below adequate threshold
        mock_adc.set_mock_value(1, 0.686)

        # Shorten operation duration and moisture check interval in the controller module
        import app.controllers.irrigation_controller as ic_mod
        monkeypatch.setattr(ic_mod, 'MAX_OPERATION_DURATION_SEC', 1, raising=False)
        monkeypatch.setattr(ic_mod, 'MOISTURE_CHECK_INTERVAL_SEC', 0.1, raising=False)
        
        original_decision = irrigation_controller.decision_engine.should_irrigate

        def always_irrigate(moisture, weather):
            return {
                'should_irrigate': True,
                'reason': 'test-allow',
                'user_message': 'ok',
                'confidence': 1.0,
            }

        irrigation_controller.decision_engine.should_irrigate = always_irrigate

        zone_config = {'slope': 0.0, 'base_pressure': 200.0}
        result = irrigation_controller.start_irrigation(1, zone_config)
        assert result['success'] is True
        
        start = time.time()
        while irrigation_controller.is_running and (time.time() - start) < 5:
            time.sleep(0.1)
        
        assert irrigation_controller.is_running is False

        irrigation_controller.decision_engine.should_irrigate = original_decision

    def test_irrigation_soil_moisture_read_failure_during_cycle(self, irrigation_controller, mock_adc, monkeypatch):
        """Test errors during soil moisture reads are logged but do not crash the cycle."""
        # Start with low moisture
        mock_adc.set_mock_value(1, 0.686)
        zone_config = {'slope': 0.0, 'base_pressure': 200.0}
        
        # Let first read (inside start_irrigation) succeed, then fail in cycle
        original_read = irrigation_controller.soil_moisture_sensors[1].read_standardized
        call_count = {'n': 0}

        def flaky_read():
            call_count['n'] += 1
            if call_count['n'] == 1:
                return original_read()
            raise Exception('sensor read failed')

        irrigation_controller.soil_moisture_sensors[1].read_standardized = flaky_read

        import app.controllers.irrigation_controller as ic_mod
        monkeypatch.setattr(ic_mod, 'MAX_OPERATION_DURATION_SEC', 1, raising=False)
        monkeypatch.setattr(ic_mod, 'MOISTURE_CHECK_INTERVAL_SEC', 0.1, raising=False)

        original_decision = irrigation_controller.decision_engine.should_irrigate

        def always_irrigate(moisture, weather):
            return {
                'should_irrigate': True,
                'reason': 'test-allow',
                'user_message': 'ok',
                'confidence': 1.0,
            }

        irrigation_controller.decision_engine.should_irrigate = always_irrigate

        result = irrigation_controller.start_irrigation(1, zone_config)
        assert result['success'] is True

        start = time.time()
        while irrigation_controller.is_running and (time.time() - start) < 5:
            time.sleep(0.1)

        assert irrigation_controller.is_running is False

        irrigation_controller.decision_engine.should_irrigate = original_decision

