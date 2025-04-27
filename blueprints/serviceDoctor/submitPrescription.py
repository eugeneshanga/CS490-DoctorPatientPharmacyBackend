# blueprints/prescriptions.py

from flask import Blueprint, request, jsonify
import mysql.connector
from config import DB_CONFIG

prescriptions_bp = Blueprint('prescriptions', __name__, url_prefix='/api/prescriptions')

@prescriptions_bp.route('/drugs', methods=['GET'])
def list_drugs():
    """
    Fetch the master list of the 5 weight-loss drugs.
    Response: [
      { "drug_id": 1, "name": "Metformin",    "description": "..." },
      { "drug_id": 2, "name": "Orlistat",     "description": "..." },
      …
    ]
    """
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT drug_id, name, description
              FROM weight_loss_drugs
            ORDER BY drug_id
        """)
        drugs = cursor.fetchall()
        return jsonify(drugs), 200

    except mysql.connector.Error as err:
        print("❌ Error fetching drugs:", err)
        return jsonify(error="Internal server error"), 500

    finally:
        cursor.close()
        conn.close()



@prescriptions_bp.route('/request', methods=['POST'])
def request_prescription():
    """
    Doctor submits a prescription request for a patient.
    Body JSON: {
      "doctor_id":   5,
      "patient_id": 12,
      "drug_id":     3,
      "dosage":    "500mg",
      "instructions": "Take twice daily"
    }
    """
    if not request.is_json:
        return jsonify(error="Request body must be JSON"), 400

    data = request.get_json()
    # required fields
    for field in ('doctor_id','patient_id','drug_id','dosage','instructions'):
        if not data.get(field):
            return jsonify(error=f"Missing required field: {field}"), 400

    try:
        doctor_id    = int(data['doctor_id'])
        patient_id   = int(data['patient_id'])
        drug_id      = int(data['drug_id'])
        dosage       = str(data['dosage']).strip()
        instructions = str(data['instructions']).strip()
    except (ValueError, TypeError):
        return jsonify(error="doctor_id, patient_id and drug_id must be integers"), 400

    conn = None
    cursor = None
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # ensure the drug exists
        cursor.execute(
            "SELECT 1 FROM weight_loss_drugs WHERE drug_id = %s",
            (drug_id,)
        )
        if not cursor.fetchone():
            return jsonify(error=f"Drug id {drug_id} not found"), 404

        # look up patient's preferred pharmacy
        cursor.execute("""
            SELECT pharmacy_id
              FROM patient_preferred_pharmacy
             WHERE patient_id = %s
        """, (patient_id,))
        pref = cursor.fetchone()
        if not pref:
            return jsonify(
                error=f"No preferred pharmacy set for patient {patient_id}"
            ), 400

        pharmacy_id = pref['pharmacy_id']

        # now insert the prescription with that pharmacy_id
        cursor.execute("""
            INSERT INTO prescriptions
              (doctor_id, patient_id, pharmacy_id, drug_id, dosage, instructions, status)
            VALUES (%s, %s, %s, %s, %s, %s, 'pending')
        """, (
            doctor_id,
            patient_id,
            pharmacy_id,
            drug_id,
            dosage,
            instructions
        ))
        conn.commit()

        return jsonify(
          message="Prescription requested successfully",
          prescription_id=cursor.lastrowid
        ), 201

    except mysql.connector.Error as err:
        print("❌ Error creating prescription:", err)
        return jsonify(error="Internal server error"), 500

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
