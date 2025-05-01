from flask import Blueprint, request, jsonify
import mysql.connector
from config import DB_CONFIG
import sys

dispense_prescription_bp = Blueprint('dispense_prescription', __name__, url_prefix='/api/pharmacy')


def _get_pharmacy_id_for_user(user_id, cursor):
    cursor.execute("""
        SELECT pharmacy_id
          FROM pharmacies
         WHERE user_id = %s
           AND is_active = TRUE
        LIMIT 1;
    """, (user_id,))
    row = cursor.fetchone()
    return row['pharmacy_id'] if row else None


@dispense_prescription_bp.route('/prescriptions/<int:prescription_id>/dispense', methods=['POST'])
def dispense_prescription(prescription_id):
    # 1) extract and validate the pharmacy’s user_id
    user_id = request.args.get('user_id', type=int)
    if not user_id:
        return jsonify(error="user_id is required"), 400

    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        # 2) resolve pharmacy_id
        pharm_id = _get_pharmacy_id_for_user(user_id, cursor)
        if pharm_id is None:
            return jsonify(error="No active pharmacy found for that user"), 404

        # 3) fetch the prescription, ensure it belongs here and is filled
        cursor.execute("""
            SELECT patient_id, drug_id, status
              FROM prescriptions
             WHERE prescription_id = %s
               AND pharmacy_id     = %s
        """, (prescription_id, pharm_id))
        pres = cursor.fetchone()
        if not pres:
            return jsonify(error="Prescription not found or unauthorized"), 404
        if pres['status'] != 'filled':
            return jsonify(error="Prescription not ready for dispense"), 400

        patient_id = pres['patient_id']
        drug_id = pres['drug_id']

        # 4) lookup the current price for that drug
        cursor.execute("""
            SELECT price
              FROM pharmacy_drug_prices
             WHERE pharmacy_id = %s
               AND drug_id     = %s
        """, (pharm_id, drug_id))
        price_row = cursor.fetchone()
        if not price_row:
            return jsonify(error="Price not set for this drug"), 500
        amount = price_row['price']

        # 5) mark as dispensed
        cursor.execute("""
            UPDATE prescriptions
               SET status = 'dispensed'
             WHERE prescription_id = %s
               AND pharmacy_id     = %s
        """, (prescription_id, pharm_id))

        # 6) create the payment record
        cursor.execute("""
            INSERT INTO payments_pharmacy
              (pharmacy_id, patient_id, amount, is_fulfilled, payment_date)
            VALUES (%s, %s, %s, FALSE, NOW())
        """, (pharm_id, patient_id, amount))
        payment_id = cursor.lastrowid

        conn.commit()

        return jsonify(
            message="Prescription dispensed and payment created",
            prescription_id=prescription_id,
            payment_id=payment_id,
            amount=amount
        ), 200

    except mysql.connector.Error as err:
        conn.rollback()
        # log for debugging
        print(f"[ERROR] dispense_prescription exception: {err}", file=sys.stderr)
        return jsonify(error="Internal server error", detail=str(err)), 500

    finally:
        cursor.close()
        conn.close()


@dispense_prescription_bp.route('/prescriptions/filled', methods=['GET'])
def get_filled_prescriptions():
    """
    Return all prescriptions with status='filled' for the current user’s pharmacy.
    Query:  ?user_id=<pharmacy_user_id>
    Response: [
      {
        "prescription_id": 12,
        "patient_name": "Emily Williams",
        "medication_name": "Orlistat",
        "dosage": "120mg once daily",
        "requested_at": "2025-04-25T14:32:00"
      },
      …
    ]
    """
    user_id = request.args.get('user_id', type=int)
    if not user_id:
        return jsonify(error="user_id is required"), 400

    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        # resolve pharmacy_id
        pharm_id = _get_pharmacy_id_for_user(user_id, cursor)
        if pharm_id is None:
            return jsonify(error="No active pharmacy found for that user"), 404

        # fetch all filled prescriptions
        cursor.execute("""
            SELECT
              pr.prescription_id,
              CONCAT(pt.first_name, ' ', pt.last_name) AS patient_name,
              wd.name                         AS medication_name,
              pr.dosage,
              pr.created_at                   AS requested_at
            FROM prescriptions pr
            JOIN patients          pt ON pr.patient_id = pt.patient_id
            JOIN weight_loss_drugs wd ON pr.drug_id     = wd.drug_id
            WHERE pr.pharmacy_id = %s
              AND pr.status      = 'filled'
            ORDER BY pr.created_at ASC;
        """, (pharm_id,))

        rows = cursor.fetchall()
        return jsonify(rows), 200

    finally:
        cursor.close()
        conn.close()
