"""Fail-safe mechanisms for system safety."""
from typing import Dict, List, Optional, Callable
from datetime import datetime, timedelta
from app.sensors.base import BaseSensor
from app.config.config import SENSOR_FAILURE_THRESHOLD
from app.models.system_log import SystemLog, LogLevel


class SensorFailureHandler:
    """Handle sensor failures and degradation."""

    def __init__(self, db_session_factory: Callable):
        """
        Initialize sensor failure handler.
        
        Args:
            db_session_factory: Function that returns a database session
        """
        self.db_session_factory = db_session_factory
        self.sensor_failures: Dict[str, int] = {}  # sensor_id -> failure count
        self.failed_sensors: set = set()

    def check_sensor_health(self, sensor: BaseSensor) -> bool:
        """
        Check sensor health and handle failures.
        
        Args:
            sensor: Sensor instance to check
            
        Returns:
            True if sensor is healthy, False otherwise
        """
        if not sensor.is_sensor_healthy():
            if sensor.sensor_id not in self.failed_sensors:
                self.failed_sensors.add(sensor.sensor_id)
                self._log_failure(sensor.sensor_id, "Sensor marked as unhealthy")
            return False
        
        # Reset failure count if sensor is healthy
        if sensor.sensor_id in self.failed_sensors:
            self.failed_sensors.remove(sensor.sensor_id)
            self.sensor_failures.pop(sensor.sensor_id, None)
        
        return True

    def handle_sensor_failure(self, sensor_id: str, error_message: str):
        """
        Handle a sensor failure event.
        
        Args:
            sensor_id: Sensor identifier
            error_message: Error message
        """
        self.sensor_failures[sensor_id] = self.sensor_failures.get(sensor_id, 0) + 1
        
        if self.sensor_failures[sensor_id] >= SENSOR_FAILURE_THRESHOLD:
            self.failed_sensors.add(sensor_id)
            self._log_failure(sensor_id, f"Sensor failure threshold reached: {error_message}")

    def is_sensor_failed(self, sensor_id: str) -> bool:
        """Check if a sensor has failed."""
        return sensor_id in self.failed_sensors

    def get_failed_sensors(self) -> List[str]:
        """Get list of failed sensor IDs."""
        return list(self.failed_sensors)

    def _log_failure(self, sensor_id: str, message: str):
        """Log sensor failure."""
        try:
            db = next(self.db_session_factory())
            log = SystemLog(
                log_level=LogLevel.ERROR,
                component='sensor_failure_handler',
                message=f"Sensor {sensor_id}: {message}",
                sensor_id=sensor_id
            )
            db.add(log)
            db.commit()
            db.close()
        except Exception as e:
            print(f"Error logging sensor failure: {str(e)}")


class AbnormalReadingHandler:
    """Handle abnormal sensor readings."""

    def __init__(self, db_session_factory: Callable):
        """
        Initialize abnormal reading handler.
        
        Args:
            db_session_factory: Function that returns a database session
        """
        self.db_session_factory = db_session_factory
        self.abnormal_readings: Dict[str, List[datetime]] = {}  # sensor_id -> list of timestamps

    def check_reading(self, sensor_id: str, value: float, min_value: float, max_value: float) -> bool:
        """
        Check if a reading is abnormal.
        
        Args:
            sensor_id: Sensor identifier
            value: Reading value
            min_value: Minimum expected value
            max_value: Maximum expected value
            
        Returns:
            True if reading is normal, False if abnormal
        """
        if value < min_value or value > max_value:
            # Record abnormal reading
            if sensor_id not in self.abnormal_readings:
                self.abnormal_readings[sensor_id] = []
            
            self.abnormal_readings[sensor_id].append(datetime.now())
            
            # Keep only last hour of readings
            cutoff = datetime.now() - timedelta(hours=1)
            self.abnormal_readings[sensor_id] = [
                ts for ts in self.abnormal_readings[sensor_id] if ts > cutoff
            ]
            
            # Log if too many abnormal readings
            if len(self.abnormal_readings[sensor_id]) > 5:
                self._log_abnormal(sensor_id, f"Multiple abnormal readings: {value} (range: {min_value}-{max_value})")
            
            return False
        
        return True

    def _log_abnormal(self, sensor_id: str, message: str):
        """Log abnormal reading."""
        try:
            db = next(self.db_session_factory())
            log = SystemLog(
                log_level=LogLevel.WARNING,
                component='abnormal_reading_handler',
                message=f"Sensor {sensor_id}: {message}",
                sensor_id=sensor_id
            )
            db.add(log)
            db.commit()
            db.close()
        except Exception as e:
            print(f"Error logging abnormal reading: {str(e)}")


class EmergencyStop:
    """Emergency stop mechanism."""

    def __init__(self):
        """Initialize emergency stop."""
        self.is_emergency_stopped = False
        self.stop_reason: Optional[str] = None
        self.stop_time: Optional[datetime] = None

    def trigger_emergency_stop(self, reason: str):
        """
        Trigger emergency stop.
        
        Args:
            reason: Reason for emergency stop
        """
        self.is_emergency_stopped = True
        self.stop_reason = reason
        self.stop_time = datetime.now()

    def clear_emergency_stop(self):
        """Clear emergency stop condition."""
        self.is_emergency_stopped = False
        self.stop_reason = None
        self.stop_time = None

    def is_stopped(self) -> bool:
        """Check if system is emergency stopped."""
        return self.is_emergency_stopped

    def get_status(self) -> Dict:
        """Get emergency stop status."""
        return {
            'is_stopped': self.is_emergency_stopped,
            'reason': self.stop_reason,
            'stop_time': self.stop_time.isoformat() if self.stop_time else None
        }


class HealthMonitor:
    """Monitor overall system health."""

    def __init__(self, sensors: Dict[str, BaseSensor], emergency_stop: EmergencyStop,
                 db_session_factory: Callable):
        """
        Initialize health monitor.
        
        Args:
            sensors: Dictionary of sensors to monitor
            emergency_stop: Emergency stop instance
            db_session_factory: Function that returns a database session
        """
        self.sensors = sensors
        self.emergency_stop = emergency_stop
        self.db_session_factory = db_session_factory
        self.last_health_check = datetime.now()
        self.health_check_interval = timedelta(minutes=5)

    def check_system_health(self) -> Dict:
        """
        Perform system health check.
        
        Returns:
            Dictionary with health status
        """
        try:
            return self._check_system_health_internal()
        except Exception as e:
            # Catch any unhandled exceptions and return safe response
            print(f"CRITICAL: Unhandled error in check_system_health: {e}")
            import traceback
            traceback.print_exc()
            return {
                'overall_status': 'error',
                'sensor_health': {},
                'emergency_stop': {'is_stopped': False, 'reason': None, 'stop_time': None},
                'timestamp': datetime.now().isoformat(),
                'error': str(e),
                'error_type': type(e).__name__
            }
    
    def _check_system_health_internal(self) -> Dict:
        """
        Internal method to perform system health check.
        
        Returns:
            Dictionary with health status
        """
        health_status = {
            'overall_status': 'healthy',
            'sensor_health': {},
            'emergency_stop': {},
            'timestamp': datetime.now().isoformat()
        }
        
        # Get emergency stop status with error handling
        try:
            emergency_status = self.emergency_stop.get_status()
            health_status['emergency_stop'] = emergency_status
        except Exception as e:
            print(f"Error getting emergency stop status: {e}")
            import traceback
            traceback.print_exc()
            health_status['emergency_stop'] = {
                'is_stopped': False,
                'reason': None,
                'stop_time': None,
                'error': str(e)
            }
        
        # Check sensor health
        failed_sensors = []
        try:
            # Ensure self.sensors is a dict and not None
            if not isinstance(self.sensors, dict):
                print(f"Warning: self.sensors is not a dict, type: {type(self.sensors)}")
                self.sensors = {}
            
            # Convert sensor items to list to avoid iteration issues
            sensor_items = list(self.sensors.items()) if self.sensors else []
            print(f"Checking {len(sensor_items)} sensors...")
            
            for idx, (sensor_id, sensor) in enumerate(sensor_items):
                print(f"Processing sensor {idx+1}/{len(sensor_items)}: {sensor_id} (type: {type(sensor_id)})")
                try:
                    # Call is_sensor_healthy with error handling
                    try:
                        is_healthy = sensor.is_sensor_healthy()
                        if not isinstance(is_healthy, bool):
                            print(f"Warning: sensor {sensor_id} returned non-boolean health status: {type(is_healthy)}")
                            is_healthy = bool(is_healthy)
                    except Exception as e:
                        print(f"Error calling is_sensor_healthy for {sensor_id}: {e}")
                        import traceback
                        traceback.print_exc()
                        is_healthy = False
                    
                    sensor_info = {
                        'healthy': is_healthy,
                    }
                    # Some sensors (like weather) may not have zone_id
                    if hasattr(sensor, 'zone_id') and sensor.zone_id is not None:
                        # Ensure zone_id is always an int to avoid type comparison errors
                        try:
                            zone_id_val = sensor.zone_id
                            # Convert to int if possible, otherwise keep as string
                            if isinstance(zone_id_val, (int, float)):
                                sensor_info['zone_id'] = int(zone_id_val)
                            elif isinstance(zone_id_val, str):
                                try:
                                    sensor_info['zone_id'] = int(zone_id_val)
                                except (ValueError, TypeError):
                                    sensor_info['zone_id'] = zone_id_val  # Keep as string if can't convert
                            else:
                                sensor_info['zone_id'] = str(zone_id_val)
                        except Exception as e:
                            print(f"Error processing zone_id for {sensor_id}: {e}")
                            sensor_info['zone_id'] = None
                    
                    health_status['sensor_health'][sensor_id] = sensor_info
                    
                    if not is_healthy:
                        failed_sensors.append(str(sensor_id))  # Ensure sensor_id is string
                except Exception as e:
                    # If sensor check fails, mark as unhealthy but don't crash
                    print(f"Error processing sensor {sensor_id}: {e}")
                    import traceback
                    traceback.print_exc()
                    health_status['sensor_health'][str(sensor_id)] = {
                        'healthy': False,
                        'error': str(e)
                    }
                    failed_sensors.append(str(sensor_id))
        except Exception as e:
            # If iterating sensors fails, log but continue
            print(f"Error checking sensors: {e}")
            import traceback
            traceback.print_exc()
        
        # Determine overall status - ensure all values are ints for comparison
        try:
            # Ensure we have valid integers for comparison
            num_sensors = int(len(self.sensors)) if self.sensors and isinstance(self.sensors, dict) else 0
            num_failed = int(len(failed_sensors)) if failed_sensors else 0
            
            # Check emergency stop status safely
            try:
                is_stopped = bool(self.emergency_stop.is_stopped())
            except Exception as e:
                print(f"Error checking emergency stop: {e}")
                is_stopped = False
            
            if is_stopped:
                health_status['overall_status'] = 'emergency_stopped'
            elif num_sensors > 0:
                # Ensure we're comparing ints
                threshold = float(num_sensors) * 0.5
                if num_failed > threshold:  # More than 50% sensors failed
                    health_status['overall_status'] = 'degraded'
                    health_status['failed_sensors'] = failed_sensors
                elif num_failed > 0:
                    health_status['overall_status'] = 'warning'
                    health_status['failed_sensors'] = failed_sensors
        except Exception as e:
            # If status determination fails, just mark as healthy but log error
            print(f"Error determining overall status: {e}")
            import traceback
            traceback.print_exc()
            health_status['overall_status'] = 'healthy'  # Default to healthy if we can't determine
        
        self.last_health_check = datetime.now()
        
        return health_status

    def should_perform_health_check(self) -> bool:
        """Check if health check should be performed."""
        return datetime.now() - self.last_health_check >= self.health_check_interval

