from flask import Blueprint, jsonify, request
import mysql.connector
from config import DB_CONFIG

patient_dashboard_bp = Blueprint('patient_dashboard', __name__, url_prefix='/api/patient-dashboard')


@patient_dashboard_bp.route('/details', methods=['GET'])
def get_patient_details():
    """
    Endpoint to retrieve patient details for a given user_id.
    Expects a query parameter 'user_id'. Converts user_id to patient_id,
    then retrieves first_name, last_name, and patient_id from the patients table.
    """
    user_id = request.args.get('user_id', type=int)
    if not user_id:
        return jsonify({"error": "user_id query parameter is required"}), 400

    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            "SELECT patient_id, first_name, last_name FROM patients WHERE user_id = %s",
            (user_id,)
        )
        patient = cursor.fetchone()
        if not patient:
            return jsonify({"error": "Patient not found for given user_id"}), 404

        cursor.close()
        connection.close()

        return jsonify({"patient": patient}), 200

    except mysql.connector.Error as err:
        return jsonify({"error": str(err)}), 500
