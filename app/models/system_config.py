"""System configuration model for storing key-value configuration."""
from sqlalchemy import Column, Integer, String, Float, Text
from app.config.database import Base


class SystemConfig(Base):
    """Model for system configuration key-value pairs."""
    __tablename__ = 'system_configs'

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(Text, nullable=False)  # Store as text, convert as needed
    description = Column(String(500), nullable=True)  # Description of the config value

    def __repr__(self):
        return f"<SystemConfig(key={self.key}, value={self.value})>"

    def get_float(self):
        """Get value as float."""
        try:
            return float(self.value)
        except (ValueError, TypeError):
            return None

    def get_int(self):
        """Get value as integer."""
        try:
            return int(self.value)
        except (ValueError, TypeError):
            return None

    def get_bool(self):
        """Get value as boolean."""
        return self.value.lower() in ('true', '1', 'yes', 'on')

