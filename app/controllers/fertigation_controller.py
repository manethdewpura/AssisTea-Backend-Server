"""Fertigation cycle controller."""
import time
import threading
from typing import Dict, Optional, Callable
from datetime import datetime
from app.hydraulics.valve_controller import HydraulicValveController
from app.hardware.tank_valve_controller import TankValveController
from app.sensors.tank_level import TankLevelSensor
from app.sensors.weather import WeatherReader
from app.config.config import TANK_EMPTY_LEVEL_CM, TANK_FULL_LEVEL_CM, MAX_OPERATION_DURATION_SEC
from app.models.operational_log import OperationalLog, OperationType, OperationStatus
from app.models.system_log import SystemLog, LogLevel


class FertigationController:
    """Controller for fertigation cycles."""

    def __init__(self, valve_controller: HydraulicValveController,
                 tank_valve_controller: TankValveController,
                 tank_level_sensor: TankLevelSensor,
                 db_session_factory: Callable,
                 weather_reader: Optional[WeatherReader] = None,
                 check_weather: bool = False):
        """
        Initialize fertigation controller.
        
        Args:
            valve_controller: Zone valve controller instance
            tank_valve_controller: Tank valve controller for inlet/outlet
            tank_level_sensor: Tank level sensor instance
            db_session_factory: Function that returns a database session
            weather_reader: Optional weather reader instance for weather checking
            check_weather: Whether to check weather conditions before fertigation (default: False)
        """
        self.valve_controller = valve_controller
        self.tank_valve_controller = tank_valve_controller
        self.tank_level_sensor = tank_level_sensor
        self.db_session_factory = db_session_factory
        self.weather_reader = weather_reader
        self.check_weather = check_weather
        
        self.is_running = False
        self.current_zone: Optional[int] = None
        self.operation_thread: Optional[threading.Thread] = None
        self.start_time: Optional[datetime] = None

    def start_fertigation(self, zone_id: int) -> Dict[str, any]:
        """
        Start fertigation cycle for a zone.
        
        Args:
            zone_id: Zone ID to fertigate
            
        Returns:
            Dictionary with operation status
        """
        if self.is_running:
            return {
                'success': False,
                'message': 'Fertigation already in progress',
                'current_zone': self.current_zone
            }
        
        # Check weather if enabled
        if self.check_weather and self.weather_reader:
            try:
                weather_data = self.weather_reader.read_standardized()
                # Allow fertigation in clear or cloudy conditions, but warn about rainy conditions
                if weather_data['condition'] == 'rainy':
                    return {
                        'success': False,
                        'message': f'Weather condition is {weather_data["condition"]}, not suitable for fertigation',
                        'weather_condition': weather_data['condition']
                    }
            except Exception as e:
                self._log_system(LogLevel.WARNING, 'fertigation_controller',
                               f'Failed to check weather: {str(e)}, proceeding with fertigation')
        
        # Start fertigation in background thread
        self.is_running = True
        self.current_zone = zone_id
        self.start_time = datetime.now()
        
        self.operation_thread = threading.Thread(
            target=self._fertigation_cycle,
            args=(zone_id,),
            daemon=True
        )
        self.operation_thread.start()
        
        return {
            'success': True,
            'message': f'Fertigation started for zone {zone_id}',
            'zone_id': zone_id
        }

    def _fertigation_cycle(self, zone_id: int):
        """Execute fertigation cycle."""
        try:
            # Log operation start
            self._log_operation(zone_id, OperationStatus.STARTED)
            
            # Step 1: Open zone valve and close all others
            if not self.valve_controller.open_zone(zone_id, close_others=True):
                raise Exception(f'Failed to open valve for zone {zone_id}')
            
            self._log_system(LogLevel.INFO, 'fertigation_controller',
                           f'Zone {zone_id} valve opened')
            
            # Step 2: Fill fertilizer tank (open inlet solenoid)
            self._log_system(LogLevel.INFO, 'fertigation_controller',
                           'Opening tank inlet valve to fill tank')
            self.tank_valve_controller.open_inlet()
            
            # Wait for tank to fill
            tank_filled = False
            fill_start_time = time.time()
            fill_timeout = 300  # 5 minutes max for filling
            
            while time.time() - fill_start_time < fill_timeout:
                try:
                    level_data = self.tank_level_sensor.read_standardized()
                    level_cm = level_data['value']
                    
                    if level_cm >= TANK_FULL_LEVEL_CM - 2:  # Allow 2cm tolerance
                        tank_filled = True
                        self._log_system(LogLevel.INFO, 'fertigation_controller',
                                       f'Tank filled to {level_cm:.1f} cm')
                        break
                except Exception as e:
                    self._log_system(LogLevel.WARNING, 'fertigation_controller',
                                   f'Error reading tank level during fill: {str(e)}')
                
                time.sleep(2)  # Check every 2 seconds
            
            # Close inlet valve
            self.tank_valve_controller.close_inlet()
            
            if not tank_filled:
                raise Exception('Tank filling timeout or failed')
            
            # Step 3: Flush fertilizer (open outlet solenoid)
            self._log_system(LogLevel.INFO, 'fertigation_controller',
                           'Opening tank outlet valve to flush fertilizer')
            self.tank_valve_controller.open_outlet()
            
            # Update status
            self._log_operation(zone_id, OperationStatus.IN_PROGRESS)
            
            # Monitor tank level until empty
            operation_start_time = time.time()
            initial_tank_level = TANK_FULL_LEVEL_CM
            
            while self.is_running:
                # Check for timeout
                if time.time() - operation_start_time > MAX_OPERATION_DURATION_SEC:
                    self._log_system(LogLevel.WARNING, 'fertigation_controller',
                                   f'Fertigation timeout reached for zone {zone_id}')
                    break
                
                try:
                    level_data = self.tank_level_sensor.read_standardized()
                    level_cm = level_data['value']
                    
                    # Check if tank is empty
                    if level_cm <= TANK_EMPTY_LEVEL_CM + 2:  # Allow 2cm tolerance
                        self._log_system(LogLevel.INFO, 'fertigation_controller',
                                       f'Tank emptied to {level_cm:.1f} cm')
                        break
                except Exception as e:
                    self._log_system(LogLevel.WARNING, 'fertigation_controller',
                                   f'Error reading tank level during flush: {str(e)}')
                
                time.sleep(2)  # Check every 2 seconds
            
            # Close outlet valve
            self.tank_valve_controller.close_outlet()
            
            # Stop fertigation
            self._stop_fertigation(zone_id, initial_tank_level)
            
        except Exception as e:
            self._log_system(LogLevel.ERROR, 'fertigation_controller',
                           f'Fertigation cycle error for zone {zone_id}: {str(e)}')
            self._log_operation(zone_id, OperationStatus.FAILED)
            
            # Ensure valves are closed
            self.tank_valve_controller.close_all()
            self.valve_controller.close_zone(zone_id)
            
            self.is_running = False
            self.current_zone = None

    def _stop_fertigation(self, zone_id: int, initial_tank_level: float):
        """Stop fertigation and clean up."""
        # Ensure all valves are closed
        self.tank_valve_controller.close_all()
        self.valve_controller.close_zone(zone_id)
        
        # Get final tank level
        final_tank_level = TANK_EMPTY_LEVEL_CM
        try:
            level_data = self.tank_level_sensor.read_standardized()
            final_tank_level = level_data['value']
        except:
            pass
        
        # Calculate duration and fertilizer volume
        duration = (datetime.now() - self.start_time).total_seconds() if self.start_time else 0.0
        fertilizer_volume = max(0.0, initial_tank_level - final_tank_level)  # Simplified calculation
        
        # Log completion
        self._log_operation(zone_id, OperationStatus.COMPLETED,
                           duration=duration,
                           fertilizer_volume=fertilizer_volume)
        
        self.is_running = False
        self.current_zone = None

    def stop_fertigation(self) -> Dict[str, any]:
        """Stop current fertigation cycle."""
        if not self.is_running:
            return {
                'success': False,
                'message': 'No fertigation in progress'
            }
        
        self.is_running = False
        
        if self.current_zone:
            # Get initial tank level for logging
            initial_level = TANK_FULL_LEVEL_CM
            try:
                level_data = self.tank_level_sensor.read_standardized()
                initial_level = level_data['value']
            except:
                pass
            
            self._stop_fertigation(self.current_zone, initial_level)
            self._log_operation(self.current_zone, OperationStatus.STOPPED)
        
        return {
            'success': True,
            'message': 'Fertigation stopped'
        }

    def get_status(self) -> Dict[str, any]:
        """Get fertigation controller status."""
        tank_level = None
        try:
            level_data = self.tank_level_sensor.read_standardized()
            tank_level = level_data['value']
        except:
            pass
        
        return {
            'is_running': self.is_running,
            'current_zone': self.current_zone,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'tank_level_cm': tank_level
        }

    def _log_operation(self, zone_id: int, status: OperationStatus, **kwargs):
        """Log operation to database."""
        try:
            db = next(self.db_session_factory())
            log = OperationalLog(
                operation_type=OperationType.FERTIGATION,
                zone_id=zone_id,
                status=status,
                duration=kwargs.get('duration'),
                fertilizer_volume=kwargs.get('fertilizer_volume'),
                notes=kwargs.get('notes')
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

