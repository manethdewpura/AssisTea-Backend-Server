# AssisTea Backend Server

A smart irrigation and fertigation control system backend that manages automated watering cycles, fertilizer distribution, and sensor monitoring for agricultural applications. The system uses machine learning weather predictions, fuzzy logic decision-making, and real-time sensor data to optimize irrigation schedules.

## Tech Stack

- **Backend Framework**: Flask 3.1.2
- **Database**: SQLite with SQLAlchemy 2.0.44
- **Machine Learning**: TensorFlow 2.14.0+ (TensorFlow Lite for Raspberry Pi deployment)
- **Fuzzy Logic**: scikit-fuzzy 0.5.0
- **Hardware Interfaces**: 
  - Adafruit CircuitPython libraries (ADS1115 ADC, I2C communication)
  - GPIO abstraction layer (supports mock and real hardware)
- **API**: Flask-CORS for cross-origin requests
- **Scientific Computing**: NumPy, SciPy

## Branching Strategy

This project follows a feature branch workflow where new features are developed in separate branches and merged into the main branch via pull requests. The main branch represents the stable production-ready code.

## How to Run the Project

### Prerequisites

- Python 3.8 or higher
- Virtual environment (venv)
- Required hardware (for production) or mock mode (for development)

### Setup

1. **Clone the repository** (if not already done):
   ```bash
   git clone <repository-url>
   cd AssisTea-Backend-Server
   ```

2. **Create and activate a virtual environment**:
   ```bash
   # Windows
   python -m venv venv
   venv\Scripts\activate

   # Linux/Mac
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables** (optional):
   - The system automatically detects if it's running on Raspberry Pi
   - For development on Windows/Mac, hardware will run in mock mode automatically
   - To force mock hardware mode: Set `USE_MOCK_HARDWARE=true` environment variable
   - To use real GPIO on non-Pi systems: Set `USE_REAL_GPIO=true` environment variable

### Running the Application

**Start the Flask server**:
```bash
python main.py
```

The server will start on `http://0.0.0.0:5000` (accessible at `http://localhost:5000`).

### API Endpoints

- `GET /` - Root endpoint with system status
- `GET /health` - Health check endpoint
- API routes are available under `/api/` prefix (irrigation, fertigation, sensors, schedules, etc.)

## Setup Requirements

### Development Environment

- **Python**: 3.8+ installed
- **Virtual Environment**: Isolated Python environment (venv)
- **Dependencies**: All packages listed in `requirements.txt`
- **Database**: SQLite databases are automatically created in the `database/` directory on first run
- **Hardware Mode**: Mock hardware is used by default on non-Raspberry Pi systems

### Production Environment (Raspberry Pi)

- **Raspberry Pi** with GPIO access
- **Hardware Components**:
  - ADS1115 ADC for analog sensor readings (soil moisture, pressure)
  - GPIO pins configured for pumps and solenoid valves
  - Ultrasonic sensor for tank level monitoring
  - I2C bus enabled for ADC communication
- **TensorFlow Lite Runtime**: For Raspberry Pi, uncomment `tflite-runtime>=2.14.0` in `requirements.txt` and use it instead of full TensorFlow
- **Environment Variables**: Configure GPIO pins and sensor channels via environment variables (see `app/config/config.py`)

### Database Initialization

The system automatically initializes two SQLite databases on first run:
- `database/irrigation_system.db` - Main system database (zones, schedules, logs)
- `database/weather.db` - Weather records database

No manual database setup is required.

### Model Files

The ML models are located in the `models/` directory:
- `weather_1d_cnn_model.keras` - Weather prediction model
- `weather_model.tflite` - TensorFlow Lite version for deployment

These files should be present for ML predictions to work correctly.

