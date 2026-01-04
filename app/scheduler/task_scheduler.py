"""Task scheduler for automated irrigation/fertigation cycles."""
import threading
import time
from datetime import datetime, time as dt_time
from typing import Dict, Callable, Optional
from app.config.database import get_db
from app.models.schedule import IrrigationSchedule, FertigationSchedule
from app.config.config import (
    ZONE_ID, ZONE_ALTITUDE_M, ZONE_SLOPE_DEGREES, ZONE_BASE_PRESSURE_KPA, SCHEDULE_TIMEZONE
)

# Timezone handling
try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except ImportError:
    try:
        from backports.zoneinfo import ZoneInfo  # Python 3.8 with backports
    except ImportError:
        # Fallback to pytz if zoneinfo not available
        try:
            import pytz
            ZoneInfo = None  # Will use pytz instead
        except ImportError:
            ZoneInfo = None
            pytz = None


class TaskScheduler:
    """Background scheduler for irrigation and fertigation tasks."""

    def __init__(self, irrigation_callback: Callable, fertigation_callback: Callable):
        """
        Initialize task scheduler.
        
        Args:
            irrigation_callback: Function to call when irrigation schedule triggers (zone_id, zone_config)
            fertigation_callback: Function to call when fertigation schedule triggers (zone_id)
        """
        self.irrigation_callback = irrigation_callback
        self.fertigation_callback = fertigation_callback
        self.is_running = False
        self.scheduler_thread: Optional[threading.Thread] = None
        self.check_interval = 60  # Check schedules every 60 seconds
        
        # Setup timezone for schedule comparisons
        self.timezone = self._get_timezone()

    def start(self):
        """Start the scheduler."""
        if self.is_running:
            return
        
        self.is_running = True
        self.scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self.scheduler_thread.start()

    def stop(self):
        """Stop the scheduler."""
        self.is_running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)

    def _scheduler_loop(self):
        """Main scheduler loop."""
        while self.is_running:
            try:
                self._check_and_trigger_schedules()
            except Exception as e:
                print(f"Scheduler error: {str(e)}")
            
            time.sleep(self.check_interval)

    def _get_timezone(self):
        """Get timezone object for schedule comparisons."""
        if SCHEDULE_TIMEZONE:
            # Try zoneinfo first (Python 3.9+)
            if ZoneInfo is not None:
                try:
                    return ZoneInfo(SCHEDULE_TIMEZONE)
                except Exception as e:
                    print(f"Warning: Could not load timezone '{SCHEDULE_TIMEZONE}' with zoneinfo: {e}")
                    # Fall through to pytz
                    pass
            
            # Fallback to pytz
            if pytz is not None:
                try:
                    return pytz.timezone(SCHEDULE_TIMEZONE)
                except Exception as e:
                    print(f"Warning: Could not load timezone '{SCHEDULE_TIMEZONE}' with pytz: {e}")
                    print("Warning: Using system local time instead")
                    return None
            else:
                print("Warning: timezone library not available, using system local time")
                return None
        else:
            # Use system local timezone
            return None
    
    def _get_local_now(self) -> datetime:
        """Get current datetime in the configured timezone."""
        if self.timezone is not None:
            if ZoneInfo is not None:
                # zoneinfo returns timezone-aware datetime
                return datetime.now(self.timezone)
            elif pytz is not None:
                # pytz returns timezone-aware datetime
                return datetime.now(self.timezone)
        # Fallback to system local time (naive datetime)
        return datetime.now()
    
    def _check_and_trigger_schedules(self):
        """Check schedules and trigger if needed."""
        now = self._get_local_now()
        # Extract date and time components in local timezone
        # For timezone-aware datetimes, we can directly use weekday() and date()
        # as they work correctly with timezone-aware datetimes
        current_day = now.weekday()  # 0=Monday, 6=Sunday
        current_date = now.date()
        
        db = next(get_db())
        
        try:
            # Check irrigation schedules
            irrigation_schedules = db.query(IrrigationSchedule).filter_by(enabled=True).all()
            for schedule in irrigation_schedules:
                if schedule.day_of_week == current_day:
                    # Check if time matches (within check_interval window)
                    schedule_time = schedule.time
                    # Combine schedule time with current date in local timezone
                    schedule_datetime = datetime.combine(current_date, schedule_time)
                    if now.tzinfo is not None:
                        # Make timezone-aware if needed
                        if ZoneInfo is not None:
                            schedule_datetime = schedule_datetime.replace(tzinfo=self.timezone)
                        elif pytz is not None:
                            schedule_datetime = self.timezone.localize(schedule_datetime)
                    
                    time_diff = abs((schedule_datetime - now).total_seconds())
                    
                    if time_diff <= self.check_interval:
                        # Check if already run today (compare dates in local timezone)
                        if schedule.last_run is None:
                            should_run = True
                        else:
                            # Convert last_run to local timezone for comparison
                            last_run_local = self._convert_to_local(schedule.last_run)
                            should_run = last_run_local.date() < current_date
                        
                        if should_run:
                            # Trigger irrigation
                            self._trigger_irrigation(schedule, db)
            
            # Check fertigation schedules
            fertigation_schedules = db.query(FertigationSchedule).filter_by(enabled=True).all()
            for schedule in fertigation_schedules:
                if schedule.day_of_week == current_day:
                    schedule_time = schedule.time
                    schedule_datetime = datetime.combine(current_date, schedule_time)
                    if now.tzinfo is not None:
                        if ZoneInfo is not None:
                            schedule_datetime = schedule_datetime.replace(tzinfo=self.timezone)
                        elif pytz is not None:
                            schedule_datetime = self.timezone.localize(schedule_datetime)
                    
                    time_diff = abs((schedule_datetime - now).total_seconds())
                    
                    if time_diff <= self.check_interval:
                        if schedule.last_run is None:
                            should_run = True
                        else:
                            last_run_local = self._convert_to_local(schedule.last_run)
                            should_run = last_run_local.date() < current_date
                        
                        if should_run:
                            # Trigger fertigation
                            self._trigger_fertigation(schedule, db)
        
        finally:
            db.close()
    
    def _convert_to_local(self, dt: datetime) -> datetime:
        """Convert a datetime to local timezone for comparison."""
        if dt is None:
            return None
        
        if dt.tzinfo is None:
            # Naive datetime - assume it's already in local timezone
            return dt
        
        if self.timezone is None:
            # No timezone configured - convert to naive (system local)
            return dt.astimezone().replace(tzinfo=None)
        
        # Convert to configured timezone
        if ZoneInfo is not None:
            return dt.astimezone(self.timezone)
        elif pytz is not None:
            return dt.astimezone(self.timezone)
        else:
            return dt.astimezone().replace(tzinfo=None)

    def _trigger_irrigation(self, schedule: IrrigationSchedule, db):
        """Trigger irrigation for a schedule."""
        try:
            # Use hardcoded zone config
            zone_config = {
                'altitude': ZONE_ALTITUDE_M,
                'slope': ZONE_SLOPE_DEGREES,
                'base_pressure': ZONE_BASE_PRESSURE_KPA
            }
            
            # Call callback with hardcoded zone_id (schedule.zone_id should always be ZONE_ID)
            self.irrigation_callback(ZONE_ID, zone_config)
            
            # Update last_run with timezone-aware datetime
            schedule.last_run = self._get_local_now()
            db.commit()
            
        except Exception as e:
            print(f"Error triggering irrigation for schedule {schedule.id}: {str(e)}")

    def _trigger_fertigation(self, schedule: FertigationSchedule, db):
        """Trigger fertigation for a schedule."""
        try:
            # Call callback with hardcoded zone_id (schedule.zone_id should always be ZONE_ID)
            self.fertigation_callback(ZONE_ID)
            
            # Update last_run with timezone-aware datetime
            schedule.last_run = self._get_local_now()
            db.commit()
            
        except Exception as e:
            print(f"Error triggering fertigation for schedule {schedule.id}: {str(e)}")

