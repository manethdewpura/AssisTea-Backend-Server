from flask import Flask, jsonify, request
from database import db, init_db
from weather_routes import weather_bp
import os

app = Flask(__name__)

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
