from flask import Flask, jsonify, request

app = Flask(__name__)

@app.route('/')
def home():
    return jsonify("Backend running on Raspberry Pi")

@app.route('/sensor', methods=['POST'])
def receive_sensor_data():
    data = request.json
    print("Received data:", data)
    return jsonify({"status": "success", "received": data}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
