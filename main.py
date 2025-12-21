from flask import Flask, jsonify, request
from flask_cors import CORS
from database import db, init_db
from weather_routes import weather_bp
from ml_background_task import init_background_task
import os
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

app = Flask(__name__)

# Enable CORS for all routes
CORS(app)

# Configure SQLite database
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(basedir, "assistea.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
db.init_app(app)

# Initialize database tables
init_db(app)

# Register blueprints
app.register_blueprint(weather_bp)

# Initialize ML background task (checks for stale data every 30 minutes)
# This will automatically generate ML predictions when data is stale
try:
    init_background_task(app, check_interval_seconds=1800)  # 30 minutes
    logging.info("✓ ML background task initialized")
except Exception as e:
    logging.warning(f"ML background task not available: {e}")

@app.route('/')
def home():
    return jsonify("Backend running on Raspberry Pi with CI/CD")

@app.route('/health', methods=['GET'])
def api_health():
    """API health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'assistea-backend',
        'database': 'connected'
    }), 200

@app.route('/sensor', methods=['POST'])
def receive_sensor_data():
    data = request.json
    print("Received data:", data)
    return jsonify({"status": "success", "received": data}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
