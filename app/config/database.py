"""Database configuration and initialization."""
import os
import logging
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.ext.declarative import declarative_base

# Database path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATABASE_PATH = os.path.join(BASE_DIR, 'database', 'irrigation_system.db')

# Ensure database directory exists
os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)

# Create database engine
DATABASE_URL = f'sqlite:///{DATABASE_PATH}'
engine = create_engine(DATABASE_URL, connect_args={'check_same_thread': False}, echo=False)

# Create session factory
SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))

# Base class for models
Base = declarative_base()


def migrate_db():
    """Run database migrations to add missing columns."""
    inspector = inspect(engine)
    
    # Check if zone_configs table exists
    if 'zone_configs' in inspector.get_table_names():
        # Get existing columns
        columns = [col['name'] for col in inspector.get_columns('zone_configs')]
        
        # Add soil_moisture_sensor_channel if it doesn't exist
        if 'soil_moisture_sensor_channel' not in columns:
            logging.info("Adding missing column: soil_moisture_sensor_channel to zone_configs table")
            with engine.connect() as conn:
                conn.execute(text('ALTER TABLE zone_configs ADD COLUMN soil_moisture_sensor_channel INTEGER'))
                conn.commit()
            logging.info("✓ Migration completed: soil_moisture_sensor_channel column added")


def init_db():
    """Initialize database by creating all tables."""
    from app.models import (
        SensorLog, OperationalLog, SystemLog,
        IrrigationSchedule, FertigationSchedule,
        ZoneConfig, SystemConfig, SolenoidStatus
    )
    Base.metadata.create_all(bind=engine)
    # Run migrations after creating tables
    migrate_db()


def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

