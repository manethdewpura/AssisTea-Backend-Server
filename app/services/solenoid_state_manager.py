"""Solenoid state manager for persistent storage and retrieval."""
from typing import Optional, Dict, List
from datetime import datetime
from app.config.database import get_db
from app.models.solenoid_status import SolenoidStatus
import logging

logger = logging.getLogger(__name__)


class SolenoidStateManager:
    """Manager for tracking and persisting solenoid valve states."""

    # Default solenoids in the system
    DEFAULT_SOLENOIDS = [
        'irrigation_pump_solenoid',
        'tank_inlet_solenoid',
        'tank_outlet_solenoid',
        'fertilizer_pump_solenoid',  # For future use if needed
    ]

    def __init__(self):
        """Initialize the solenoid state manager."""
        self._initialize_default_solenoids()

    def _initialize_default_solenoids(self):
        """Initialize database with default solenoids if they don't exist."""
        try:
            db = next(get_db())
            
            for solenoid_name in self.DEFAULT_SOLENOIDS:
                existing = db.query(SolenoidStatus).filter_by(solenoid_name=solenoid_name).first()
                if not existing:
                    new_solenoid = SolenoidStatus(
                        solenoid_name=solenoid_name,
                        is_open=0,  # Default to closed
                        last_updated=datetime.now()
                    )
                    db.add(new_solenoid)
                    logger.info(f"Initialized default solenoid: {solenoid_name} (closed)")
            
            db.commit()
            db.close()
            logger.info("Default solenoids initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing default solenoids: {str(e)}")
            if db:
                db.rollback()
                db.close()

    def set_solenoid_state(self, solenoid_name: str, is_open: bool) -> bool:
        """
        Set the state of a solenoid and update the database.
        
        Args:
            solenoid_name: Name of the solenoid
            is_open: True for open, False for closed
            
        Returns:
            True if successful, False otherwise
        """
        try:
            db = next(get_db())
            
            # Check if solenoid exists, create if not
            solenoid = db.query(SolenoidStatus).filter_by(solenoid_name=solenoid_name).first()
            
            if solenoid:
                solenoid.is_open = 1 if is_open else 0
                solenoid.last_updated = datetime.now()
            else:
                # Create new solenoid entry
                solenoid = SolenoidStatus(
                    solenoid_name=solenoid_name,
                    is_open=1 if is_open else 0,
                    last_updated=datetime.now()
                )
                db.add(solenoid)
            
            db.commit()
            db.close()
            
            logger.info(f"Solenoid {solenoid_name} set to {'open' if is_open else 'closed'}")
            return True
            
        except Exception as e:
            logger.error(f"Error setting solenoid state for {solenoid_name}: {str(e)}")
            if db:
                db.rollback()
                db.close()
            return False

    def get_solenoid_state(self, solenoid_name: str) -> Optional[bool]:
        """
        Get the current state of a solenoid.
        
        Args:
            solenoid_name: Name of the solenoid
            
        Returns:
            True if open, False if closed, None if not found
        """
        try:
            db = next(get_db())
            solenoid = db.query(SolenoidStatus).filter_by(solenoid_name=solenoid_name).first()
            db.close()
            
            if solenoid:
                return solenoid.is_open == 1
            else:
                logger.warning(f"Solenoid {solenoid_name} not found in database")
                return None
                
        except Exception as e:
            logger.error(f"Error getting solenoid state for {solenoid_name}: {str(e)}")
            if db:
                db.close()
            return None

    def get_all_solenoid_states(self) -> Dict[str, bool]:
        """
        Get the current state of all solenoids.
        
        Returns:
            Dictionary mapping solenoid names to their states (True=open, False=closed)
        """
        try:
            db = next(get_db())
            solenoids = db.query(SolenoidStatus).all()
            db.close()
            
            states = {}
            for solenoid in solenoids:
                states[solenoid.solenoid_name] = solenoid.is_open == 1
            
            return states
            
        except Exception as e:
            logger.error(f"Error getting all solenoid states: {str(e)}")
            if db:
                db.close()
            return {}

    def load_all_states(self) -> Dict[str, bool]:
        """
        Load all solenoid states from database.
        Alias for get_all_solenoid_states() for clarity.
        
        Returns:
            Dictionary mapping solenoid names to their states
        """
        return self.get_all_solenoid_states()

    def add_solenoid(self, solenoid_name: str, initial_state: bool = False) -> bool:
        """
        Add a new solenoid to the tracking system.
        
        Args:
            solenoid_name: Name of the solenoid
            initial_state: Initial state (True=open, False=closed)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            db = next(get_db())
            
            # Check if already exists
            existing = db.query(SolenoidStatus).filter_by(solenoid_name=solenoid_name).first()
            if existing:
                db.close()
                logger.warning(f"Solenoid {solenoid_name} already exists")
                return False
            
            # Create new solenoid
            new_solenoid = SolenoidStatus(
                solenoid_name=solenoid_name,
                is_open=1 if initial_state else 0,
                last_updated=datetime.now()
            )
            db.add(new_solenoid)
            db.commit()
            db.close()
            
            logger.info(f"Added new solenoid: {solenoid_name} (initial state: {'open' if initial_state else 'closed'})")
            return True
            
        except Exception as e:
            logger.error(f"Error adding solenoid {solenoid_name}: {str(e)}")
            if db:
                db.rollback()
                db.close()
            return False

    def get_solenoid_info(self, solenoid_name: str) -> Optional[Dict]:
        """
        Get detailed information about a solenoid.
        
        Args:
            solenoid_name: Name of the solenoid
            
        Returns:
            Dictionary with solenoid information or None if not found
        """
        try:
            db = next(get_db())
            solenoid = db.query(SolenoidStatus).filter_by(solenoid_name=solenoid_name).first()
            db.close()
            
            if solenoid:
                return {
                    'solenoid_name': solenoid.solenoid_name,
                    'is_open': solenoid.is_open == 1,
                    'last_updated': solenoid.last_updated.isoformat() if solenoid.last_updated else None
                }
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error getting solenoid info for {solenoid_name}: {str(e)}")
            if db:
                db.close()
            return None

