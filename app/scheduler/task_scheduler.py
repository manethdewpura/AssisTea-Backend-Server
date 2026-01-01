"""Task scheduler for automated irrigation/fertigation cycles."""
import threading
import time
from datetime import datetime, time as dt_time
from typing import Dict, Callable, Optional
from app.config.database import get_db
from app.models.schedule import IrrigationSchedule, FertigationSchedule


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

    def _check_and_trigger_schedules(self):
        """Check schedules and trigger if needed."""
        now = datetime.now()
        current_day = now.weekday()  # 0=Monday, 6=Sunday
        current_time = now.time()
        
        db = next(get_db())
        
        try:
            # Check irrigation schedules
            irrigation_schedules = db.query(IrrigationSchedule).filter_by(enabled=True).all()
            for schedule in irrigation_schedules:
                if schedule.day_of_week == current_day:
                    # Check if time matches (within check_interval window)
                    schedule_time = schedule.time
                    time_diff = abs((datetime.combine(now.date(), schedule_time) - now).total_seconds())
                    
                    if time_diff <= self.check_interval:
                        # Check if already run today
                        if schedule.last_run is None or schedule.last_run.date() < now.date():
                            # Trigger irrigation
                            self._trigger_irrigation(schedule, db)
            
            # Check fertigation schedules
            fertigation_schedules = db.query(FertigationSchedule).filter_by(enabled=True).all()
            for schedule in fertigation_schedules:
                if schedule.day_of_week == current_day:
                    schedule_time = schedule.time
                    time_diff = abs((datetime.combine(now.date(), schedule_time) - now).total_seconds())
                    
                    if time_diff <= self.check_interval:
                        if schedule.last_run is None or schedule.last_run.date() < now.date():
                            # Trigger fertigation
                            self._trigger_fertigation(schedule, db)
        
        finally:
            db.close()

    def _trigger_irrigation(self, schedule: IrrigationSchedule, db):
        """Trigger irrigation for a schedule."""
        try:
            # Get zone config (would need to be passed or retrieved)
            # For now, create a basic config
            zone_config = {
                'altitude': 0.0,  # Would come from ZoneConfig
                'slope': 0.0,
                'base_pressure': 200.0
            }
            
            # Call callback
            self.irrigation_callback(schedule.zone_id, zone_config)
            
            # Update last_run
            schedule.last_run = datetime.now()
            db.commit()
            
        except Exception as e:
            print(f"Error triggering irrigation for schedule {schedule.id}: {str(e)}")

    def _trigger_fertigation(self, schedule: FertigationSchedule, db):
        """Trigger fertigation for a schedule."""
        try:
            # Call callback
            self.fertigation_callback(schedule.zone_id)
            
            # Update last_run
            schedule.last_run = datetime.now()
            db.commit()
            
        except Exception as e:
            print(f"Error triggering fertigation for schedule {schedule.id}: {str(e)}")

