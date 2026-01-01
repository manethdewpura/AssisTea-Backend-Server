"""API endpoints package."""
from flask import Blueprint

api_bp = Blueprint('api', __name__, url_prefix='/api')

# Import all endpoints to register routes
from app.api import system, irrigation, fertigation, schedules, logs, alerts, sensors, zones

