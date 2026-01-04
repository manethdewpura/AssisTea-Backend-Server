"""Irrigation cycle controller."""
import time
import threading
from typing import Dict, Optional, Callable
from datetime import datetime
from app.hydraulics.pressure_calculator import PressureCalculator
from app.hydraulics.valve_controller import HydraulicValveController
from app.hydraulics.pump_controller import HydraulicPumpController
from app.decision_engine.hybrid_engine import HybridEngine
from app.sensors.soil_moisture import SoilMoistureSensor
from app.sensors.weather import WeatherReader
from app.sensors.pressure import PressureSensor
from app.config.config import (
    ADEQUATE_SOIL_MOISTURE_PERCENT, MOISTURE_CHECK_INTERVAL_SEC,
    MAX_OPERATION_DURATION_SEC
)
from app.models.operational_log import OperationalLog, OperationType, OperationStatus
from app.models.system_log import SystemLog, LogLevel


class IrrigationController:
    """Controller for irrigation cycles."""

    def __init__(self, pressure_calculator: PressureCalculator,
                 valve_controller: HydraulicValveController,
                 pump_controller: HydraulicPumpController,
                 decision_engine: HybridEngine,
                 soil_moisture_sensors: Dict[int, SoilMoistureSensor],
                 weather_reader: WeatherReader,
                 pressure_sensor: Optional[PressureSensor],
                 db_session_factory: Callable):
        """
        Initialize irrigation controller.
        
        Args:
            pressure_calculator: Pressure calculator instance
            valve_controller: Valve controller instance
            pump_controller: Pump controller instance
            decision_engine: Decision engine instance
            soil_moisture_sensors: Dictionary mapping zone_id to soil moisture sensor
            weather_reader: Weather reader instance
            pressure_sensor: System-wide irrigation pressure sensor (common for all zones)
            db_session_factory: Function that returns a database session
        """
        self.pressure_calculator = pressure_calculator
        self.valve_controller = valve_controller
        self.pump_controller = pump_controller
        self.decision_engine = decision_engine
        self.soil_moisture_sensors = soil_moisture_sensors
        self.weather_reader = weather_reader
        self.pressure_sensor = pressure_sensor
        self.db_session_factory = db_session_factory
        
        self.is_running = False
        self.current_zone: Optional[int] = None
        self.operation_thread: Optional[threading.Thread] = None
        self.start_time: Optional[datetime] = None

    def start_irrigation(self, zone_id: int, zone_config: Dict) -> Dict[str, any]:
        """
        Start irrigation cycle for a zone.
        
        Args:
            zone_id: Zone ID to irrigate
            zone_config: Zone configuration dictionary
            
        Returns:
            Dictionary with operation status
        """
        if self.is_running:
            return {
                'success': False,
                'message': 'Irrigation already in progress',
                'current_zone': self.current_zone
            }
        
        # Check weather (skip if not clear)
        try:
            weather_data = self.weather_reader.read_standardized()
        except Exception as e:
            self._log_system(LogLevel.ERROR, 'irrigation_controller',
                           f'Failed to read weather data: {str(e)}')
            return {
                'success': False,
                'message': f'Failed to retrieve weather data: {str(e)}',
                'error': 'weather_read_failed'
            }
        
        # Log weather information for tracking
        weather_source = 'ML prediction' if weather_data.get('is_ml_generated', False) else 'API'
        weather_confidence = weather_data.get('confidence_score', 1.0)
        self._log_system(LogLevel.INFO, 'irrigation_controller',
                        f'Weather check: condition={weather_data["condition"]}, '
                        f'temp={weather_data.get("temperature", "N/A")}°C, '
                        f'humidity={weather_data.get("humidity", "N/A")}%, '
                        f'source={weather_source}, confidence={weather_confidence:.2f}')
        
        if weather_data['condition'] != 'clear':
            return {
                'success': False,
                'message': f'Weather condition is {weather_data["condition"]}, not suitable for irrigation',
                'weather_condition': weather_data['condition'],
                'weather_temperature': weather_data.get('temperature'),
                'weather_humidity': weather_data.get('humidity'),
                'weather_precipitation': weather_data.get('precipitation', 0.0),
                'is_ml_generated': weather_data.get('is_ml_generated', False),
                'confidence_score': weather_data.get('confidence_score', 1.0)
            }
        
        # Check soil moisture
        if zone_id not in self.soil_moisture_sensors:
            return {
                'success': False,
                'message': f'No soil moisture sensor configured for zone {zone_id}'
            }
        
        soil_sensor = self.soil_moisture_sensors[zone_id]
        moisture_data = soil_sensor.read_standardized()
        current_moisture = moisture_data['value']
        
        # Use decision engine
        decision = self.decision_engine.should_irrigate(current_moisture, weather_data['condition'])
        
        if not decision['should_irrigate']:
            # Log skipped operation with weather info
            self._log_operation(zone_id, OperationStatus.SKIPPED, 
                              start_moisture=current_moisture,
                              weather_info=weather_data)
            return {
                'success': False,
                'message': decision['reason'],
                'current_moisture': current_moisture,
                'decision': decision,
                'weather_condition': weather_data['condition'],
                'weather_temperature': weather_data.get('temperature'),
                'weather_humidity': weather_data.get('humidity')
            }
        
        # Start irrigation in background thread
        self.is_running = True
        self.current_zone = zone_id
        self.start_time = datetime.now()
        
        self.operation_thread = threading.Thread(
            target=self._irrigation_cycle,
            args=(zone_id, zone_config, current_moisture, weather_data),
            daemon=True
        )
        self.operation_thread.start()
        
        return {
            'success': True,
            'message': f'Irrigation started for zone {zone_id}',
            'zone_id': zone_id,
            'current_moisture': current_moisture,
            'weather_condition': weather_data['condition'],
            'weather_temperature': weather_data.get('temperature'),
            'weather_humidity': weather_data.get('humidity'),
            'is_ml_generated': weather_data.get('is_ml_generated', False),
            'confidence_score': weather_data.get('confidence_score', 1.0),
            'decision': decision
        }

    def _irrigation_cycle(self, zone_id: int, zone_config: Dict, start_moisture: float, weather_data: Dict = None):
        """Execute irrigation cycle."""
        try:
            # Log operation start with weather info
            self._log_operation(zone_id, OperationStatus.STARTED, 
                              start_moisture=start_moisture,
                              weather_info=weather_data)
            
            # Calculate required pressure
            pressure_calc = self.pressure_calculator.calculate_required_pressure(
                zone_config['altitude'],
                zone_config['slope'],
                zone_config['base_pressure']
            )
            target_pressure = pressure_calc['total_required_pressure_kpa']
            
            # Open zone valve and close others
            if not self.valve_controller.open_zone(zone_id, close_others=True):
                raise Exception(f'Failed to open valve for zone {zone_id}')
            
            # Start pump with target pressure
            self.pump_controller.start_pressure_control(target_pressure)
            
            # Update status
            self._log_operation(zone_id, OperationStatus.IN_PROGRESS, start_moisture=start_moisture)
            
            # Monitor and maintain pressure while checking moisture
            soil_sensor = self.soil_moisture_sensors[zone_id]
            
            last_moisture_check = time.time()
            operation_start_time = time.time()
            
            while self.is_running:
                # Check for timeout
                if time.time() - operation_start_time > MAX_OPERATION_DURATION_SEC:
                    self._log_system(LogLevel.WARNING, 'irrigation_controller',
                                    f'Irrigation timeout reached for zone {zone_id}')
                    break
                
                # Maintain pump pressure using system-wide irrigation pressure sensor
                current_pressure = None
                if self.pressure_sensor:
                    try:
                        pressure_data = self.pressure_sensor.read_standardized()
                        current_pressure = pressure_data['value']
                    except:
                        pass
                
                self.pump_controller.maintain_pressure(current_pressure)
                
                # Check soil moisture periodically
                if time.time() - last_moisture_check >= MOISTURE_CHECK_INTERVAL_SEC:
                    try:
                        moisture_data = soil_sensor.read_standardized()
                        current_moisture = moisture_data['value']
                        
                        # Check if adequate moisture reached
                        if current_moisture >= ADEQUATE_SOIL_MOISTURE_PERCENT:
                            self._log_system(LogLevel.INFO, 'irrigation_controller',
                                           f'Adequate moisture reached for zone {zone_id}: {current_moisture:.1f}%')
                            break
                    except Exception as e:
                        self._log_system(LogLevel.ERROR, 'irrigation_controller',
                                        f'Error reading soil moisture: {str(e)}')
                    
                    last_moisture_check = time.time()
                
                time.sleep(1)  # Small delay to prevent CPU spinning
            
            # Stop irrigation
            self._stop_irrigation(zone_id, start_moisture)
            
        except Exception as e:
            self._log_system(LogLevel.ERROR, 'irrigation_controller',
                           f'Irrigation cycle error for zone {zone_id}: {str(e)}')
            self._log_operation(zone_id, OperationStatus.FAILED)
            self.is_running = False
            self.current_zone = None

    def _stop_irrigation(self, zone_id: int, start_moisture: float):
        """Stop irrigation and clean up."""
        # Stop pump
        self.pump_controller.stop_pressure_control()
        
        # Close zone valve
        self.valve_controller.close_zone(zone_id)
        
        # Get end moisture
        end_moisture = start_moisture
        if zone_id in self.soil_moisture_sensors:
            try:
                moisture_data = self.soil_moisture_sensors[zone_id].read_standardized()
                end_moisture = moisture_data['value']
            except:
                pass
        
        # Calculate duration
        duration = (datetime.now() - self.start_time).total_seconds() if self.start_time else 0.0
        
        # Get current weather for logging (optional, for completion record)
        weather_info = None
        try:
            weather_info = self.weather_reader.read_standardized()
        except:
            pass
        
        # Log completion
        self._log_operation(zone_id, OperationStatus.COMPLETED,
                           duration=duration,
                           start_moisture=start_moisture,
                           end_moisture=end_moisture,
                           weather_info=weather_info)
        
        self.is_running = False
        self.current_zone = None

    def stop_irrigation(self) -> Dict[str, any]:
        """Stop current irrigation cycle."""
        if not self.is_running:
            return {
                'success': False,
                'message': 'No irrigation in progress'
            }
        
        self.is_running = False
        
        if self.current_zone:
            # Get start moisture for logging
            start_moisture = 0.0
            if self.current_zone in self.soil_moisture_sensors:
                try:
                    moisture_data = self.soil_moisture_sensors[self.current_zone].read_standardized()
                    start_moisture = moisture_data['value']
                except:
                    pass
            
            self._stop_irrigation(self.current_zone, start_moisture)
            self._log_operation(self.current_zone, OperationStatus.STOPPED)
        
        return {
            'success': True,
            'message': 'Irrigation stopped'
        }

    def get_status(self) -> Dict[str, any]:
        """Get irrigation controller status."""
        # Get current weather information
        weather_info = None
        try:
            weather_data = self.weather_reader.read_standardized()
            weather_info = {
                'condition': weather_data.get('condition'),
                'temperature': weather_data.get('temperature'),
                'humidity': weather_data.get('humidity'),
                'precipitation': weather_data.get('precipitation', 0.0),
                'is_ml_generated': weather_data.get('is_ml_generated', False),
                'confidence_score': weather_data.get('confidence_score', 1.0)
            }
        except Exception as e:
            weather_info = {'error': str(e)}
        
        return {
            'is_running': self.is_running,
            'current_zone': self.current_zone,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'pump_status': self.pump_controller.get_status(),
            'weather': weather_info
        }

    def _log_operation(self, zone_id: int, status: OperationStatus, **kwargs):
        """Log operation to database."""
        try:
            db = next(self.db_session_factory())
            
            # Build notes string with weather info if available
            notes = kwargs.get('notes', '')
            weather_info = kwargs.get('weather_info')
            if weather_info:
                weather_note = f"Weather: {weather_info.get('condition', 'unknown')}, "
                weather_note += f"temp={weather_info.get('temperature', 'N/A')}°C, "
                weather_note += f"humidity={weather_info.get('humidity', 'N/A')}%, "
                if weather_info.get('is_ml_generated'):
                    weather_note += f"ML-generated (confidence={weather_info.get('confidence_score', 1.0):.2f})"
                else:
                    weather_note += "API data"
                notes = f"{notes}; {weather_note}" if notes else weather_note
            
            log = OperationalLog(
                operation_type=OperationType.IRRIGATION,
                zone_id=zone_id,
                status=status,
                duration=kwargs.get('duration'),
                pressure=kwargs.get('pressure'),
                flow_rate=kwargs.get('flow_rate'),
                start_moisture=kwargs.get('start_moisture'),
                end_moisture=kwargs.get('end_moisture'),
                notes=notes
            )
            db.add(log)
            db.commit()
            db.close()
        except Exception as e:
            print(f"Error logging operation: {str(e)}")

    def _log_system(self, level: LogLevel, component: str, message: str):
        """Log system event."""
        try:
            db = next(self.db_session_factory())
            log = SystemLog(
                log_level=level,
                component=component,
                message=message,
                zone_id=self.current_zone
            )
            db.add(log)
            db.commit()
            db.close()
        except Exception as e:
            print(f"Error logging system event: {str(e)}")

