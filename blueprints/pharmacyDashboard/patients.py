from flask import Blueprint, jsonify
import mysql.connector
from config import DB_CONFIG

pharmacy_patients_bp = Blueprint('pharmacy_patients', __name__)


@pharmacy_patients_bp.route('/api/pharmacy/patients', methods=['GET'])
def get_patients():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        query = """
        SELECT DISTINCT
            pa.patient_id,
            CONCAT(pa.first_name, ' ', pa.last_name) AS patient_name
        FROM prescriptions p
        JOIN patients pa ON p.patient_id = pa.patient_id
        """

        cursor.execute(query)
        patients = cursor.fetchall()

        cursor.close()
        conn.close()

        return jsonify(patients)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
