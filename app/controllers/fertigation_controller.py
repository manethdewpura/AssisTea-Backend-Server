"""Fertigation cycle controller."""
import time
import threading
from typing import Dict, Optional, Callable
from datetime import datetime
from app.hydraulics.valve_controller import HydraulicValveController
from app.hydraulics.pump_controller import HydraulicPumpController
from app.hardware.tank_valve_controller import TankValveController
from app.hardware.irrigation_pump_solenoid import IrrigationPumpSolenoid
from app.sensors.tank_level import TankLevelSensor
from app.sensors.pressure import PressureSensor
from app.sensors.weather import WeatherReader
from app.config.config import (
    TANK_EMPTY_LEVEL_CM, TANK_FULL_LEVEL_CM, MAX_OPERATION_DURATION_SEC,
    PUMP_PRESSURE_TOLERANCE_KPA
)
from app.models.operational_log import OperationalLog, OperationType, OperationStatus
from app.models.system_log import SystemLog, LogLevel


class FertigationController:
    """Controller for fertigation cycles."""

    def __init__(self, valve_controller: HydraulicValveController,
                 tank_valve_controller: TankValveController,
                 tank_level_sensor: TankLevelSensor,
                 db_session_factory: Callable,
                 weather_reader: Optional[WeatherReader] = None,
                 check_weather: bool = False,
                 pressure_sensor: Optional[PressureSensor] = None,
                 fertilizer_pump_controller: Optional[HydraulicPumpController] = None,
                 irrigation_pump_controller: Optional[HydraulicPumpController] = None,
                 irrigation_pump_solenoid: Optional[IrrigationPumpSolenoid] = None):
        """
        Initialize fertigation controller.
        
        Args:
            valve_controller: Zone valve controller instance
            tank_valve_controller: Tank valve controller for inlet/outlet
            tank_level_sensor: Tank level sensor instance
            db_session_factory: Function that returns a database session
            weather_reader: Optional weather reader instance for weather checking
            check_weather: Whether to check weather conditions before fertigation (default: False)
            pressure_sensor: Fertilizer pump pressure sensor (A3 channel) for monitoring pump pressure
            fertilizer_pump_controller: Fertilizer pump controller for flushing (GPIO 22)
            irrigation_pump_controller: Irrigation pump controller for filling (GPIO 23)
            irrigation_pump_solenoid: Irrigation pump solenoid valve controller (GPIO 24)
        """
        self.valve_controller = valve_controller
        self.tank_valve_controller = tank_valve_controller
        self.tank_level_sensor = tank_level_sensor
        self.db_session_factory = db_session_factory
        self.weather_reader = weather_reader
        self.check_weather = check_weather
        self.pressure_sensor = pressure_sensor
        self.fertilizer_pump_controller = fertilizer_pump_controller
        self.irrigation_pump_controller = irrigation_pump_controller
        self.irrigation_pump_solenoid = irrigation_pump_solenoid
        
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
        """Execute fertigation cycle with new flow."""
        try:
            # Log operation start
            self._log_operation(zone_id, OperationStatus.STARTED)
            
            # Step 1: Close all zone valves at start
            self._log_system(LogLevel.INFO, 'fertigation_controller',
                           'Closing all zone valves at start')
            self.valve_controller.close_all_zones()
            
            # Step 2: Open tank inlet solenoid for filling
            self._log_system(LogLevel.INFO, 'fertigation_controller',
                           'Opening tank inlet valve to fill tank')
            self.tank_valve_controller.open_inlet()
            
            # Step 3: Start irrigation pump to fill tank
            if self.irrigation_pump_controller:
                # Use a default pressure for filling (can be configured)
                fill_pressure = 200.0  # kPa
                self.irrigation_pump_controller.start_pressure_control(fill_pressure)
                self._log_system(LogLevel.INFO, 'fertigation_controller',
                               f'Irrigation pump started to fill tank at {fill_pressure} kPa')
            
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
            
            # Stop irrigation pump and close inlet valve
            if self.irrigation_pump_controller:
                self.irrigation_pump_controller.stop_pressure_control()
                self._log_system(LogLevel.INFO, 'fertigation_controller',
                               'Irrigation pump stopped')
            
            self.tank_valve_controller.close_inlet()
            
            if not tank_filled:
                raise Exception('Tank filling timeout or failed')
            
            # Step 4: Open tank outlet solenoid
            self._log_system(LogLevel.INFO, 'fertigation_controller',
                           'Opening tank outlet valve to flush fertilizer')
            self.tank_valve_controller.open_outlet()
            
            # Step 5: Close irrigation pump solenoid valve
            if self.irrigation_pump_solenoid:
                self.irrigation_pump_solenoid.close()
                self._log_system(LogLevel.INFO, 'fertigation_controller',
                               'Irrigation pump solenoid valve closed')
            
            # Step 6: Re-open zone valve after closing irrigation pump solenoid
            if not self.valve_controller.open_zone(zone_id, close_others=True):
                raise Exception(f'Failed to reopen valve for zone {zone_id} after closing irrigation pump solenoid')
            
            self._log_system(LogLevel.INFO, 'fertigation_controller',
                           f'Zone {zone_id} valve reopened for fertilizer delivery')
            
            # Step 7: Start fertilizer pump to flush fertilizer
            if self.fertilizer_pump_controller:
                # Use a default pressure for flushing (can be configured)
                flush_pressure = 200.0  # kPa
                self.fertilizer_pump_controller.start_pressure_control(flush_pressure)
                self._log_system(LogLevel.INFO, 'fertigation_controller',
                               f'Fertilizer pump started to flush at {flush_pressure} kPa')
            
            # Update status
            self._log_operation(zone_id, OperationStatus.IN_PROGRESS)
            
            # Monitor tank level until empty
            operation_start_time = time.time()
            initial_tank_level = TANK_FULL_LEVEL_CM
            last_pressure_check = time.time()
            
            while self.is_running:
                # Check for timeout
                if time.time() - operation_start_time > MAX_OPERATION_DURATION_SEC:
                    self._log_system(LogLevel.WARNING, 'fertigation_controller',
                                   f'Fertigation timeout reached for zone {zone_id}')
                    break
                
                # Monitor fertilizer pump pressure if sensor is available
                if self.pressure_sensor and self.fertilizer_pump_controller:
                    if time.time() - last_pressure_check >= 2.0:  # Check every 2 seconds
                        try:
                            pressure_data = self.pressure_sensor.read_standardized()
                            current_pressure = pressure_data['value']
                            
                            # Maintain pump pressure
                            self.fertilizer_pump_controller.maintain_pressure(current_pressure)
                            
                            # Log pressure if outside tolerance
                            if self.fertilizer_pump_controller.is_controlling:
                                target_pressure = self.fertilizer_pump_controller.target_pressure_kpa
                                if abs(current_pressure - target_pressure) > PUMP_PRESSURE_TOLERANCE_KPA:
                                    self._log_system(LogLevel.WARNING, 'fertigation_controller',
                                                   f'Fertilizer pump pressure deviation: {current_pressure:.1f} kPa (target: {target_pressure:.1f} kPa)')
                        except Exception as e:
                            self._log_system(LogLevel.WARNING, 'fertigation_controller',
                                           f'Error reading fertilizer pump pressure: {str(e)}')
                        
                        last_pressure_check = time.time()
                
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
                
                time.sleep(1)  # Small delay to prevent CPU spinning
            
            # Stop fertilizer pump if controller is available
            if self.fertilizer_pump_controller:
                self.fertilizer_pump_controller.stop_pressure_control()
                self._log_system(LogLevel.INFO, 'fertigation_controller',
                               'Fertilizer pump stopped')
            
            # Close outlet valve
            self.tank_valve_controller.close_outlet()
            
            # Stop fertigation
            self._stop_fertigation(zone_id, initial_tank_level)
            
        except Exception as e:
            self._log_system(LogLevel.ERROR, 'fertigation_controller',
                           f'Fertigation cycle error for zone {zone_id}: {str(e)}')
            self._log_operation(zone_id, OperationStatus.FAILED)
            
            # Stop all pumps if controllers are available
            if self.fertilizer_pump_controller:
                try:
                    self.fertilizer_pump_controller.stop_pressure_control()
                except:
                    pass
            
            if self.irrigation_pump_controller:
                try:
                    self.irrigation_pump_controller.stop_pressure_control()
                except:
                    pass
            
            # Ensure valves are closed
            self.tank_valve_controller.close_all()
            self.valve_controller.close_zone(zone_id)
            
            self.is_running = False
            self.current_zone = None

    def _stop_fertigation(self, zone_id: int, initial_tank_level: float):
        """Stop fertigation and clean up."""
        # Stop all pumps if controllers are available
        if self.fertilizer_pump_controller:
            try:
                self.fertilizer_pump_controller.stop_pressure_control()
            except:
                pass
        
        if self.irrigation_pump_controller:
            try:
                self.irrigation_pump_controller.stop_pressure_control()
            except:
                pass
        
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
        
        fertilizer_pressure = None
        if self.pressure_sensor:
            try:
                pressure_data = self.pressure_sensor.read_standardized()
                fertilizer_pressure = pressure_data['value']
            except:
                pass
        
        fertilizer_pump_status = None
        if self.fertilizer_pump_controller:
            fertilizer_pump_status = self.fertilizer_pump_controller.get_status()
        
        irrigation_pump_status = None
        if self.irrigation_pump_controller:
            irrigation_pump_status = self.irrigation_pump_controller.get_status()
        
        return {
            'is_running': self.is_running,
            'current_zone': self.current_zone,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'tank_level_cm': tank_level,
            'fertilizer_pressure_kpa': fertilizer_pressure,
            'fertilizer_pump_status': fertilizer_pump_status,
            'irrigation_pump_status': irrigation_pump_status,
            'irrigation_pump_solenoid_open': self.irrigation_pump_solenoid.is_open() if self.irrigation_pump_solenoid else None
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

