from flask import Flask, jsonify
from flask_cors import CORS

from blueprints.pharmacyDashboard.prescriptions import pharmacy_prescriptions_bp
from blueprints.pharmacyDashboard.patients import pharmacy_patients_bp
from blueprints.serviceDoctor.submitPrescription import prescriptions_bp

app = Flask(__name__)
CORS(app)

app.register_blueprint(pharmacy_prescriptions_bp)
app.register_blueprint(pharmacy_patients_bp)
app.register_blueprint(prescriptions_bp)

@app.route('/api/hello', methods=['GET'])
def hello():
    return jsonify(message="Hello World!")

if __name__ == '__main__':
    print(app.url_map)
    app.run(debug=True, port=5001)