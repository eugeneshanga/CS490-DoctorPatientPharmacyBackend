from flask import Blueprint, request, jsonify
import mysql.connector
from config import DB_CONFIG
import sys

pharmacy_queue_bp = Blueprint('pharmacy_queue', __name__, url_prefix='/api/pharmacy')


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


@pharmacy_queue_bp.route('/queue', methods=['GET'])
def get_prescription_queue():
    """Return all pending prescriptions for the current user’s pharmacy, oldest first."""
    user_id = request.args.get('user_id', type=int)
    if not user_id:
        return jsonify(error="user_id is required"), 400

    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)

    pharm_id = _get_pharmacy_id_for_user(user_id, cursor)
    if pharm_id is None:
        cursor.close()
        conn.close()
        return jsonify(error="No active pharmacy found for that user"), 404

    cursor.execute("""
        SELECT
          pr.prescription_id,
          CONCAT(pt.first_name, ' ', pt.last_name) AS patient_name,
          wd.name                         AS medication_name,
          pr.dosage,
          pr.created_at                   AS requested_at
        FROM prescriptions pr
        JOIN patients           pt ON pr.patient_id  = pt.patient_id
        JOIN weight_loss_drugs  wd ON pr.drug_id      = wd.drug_id
        WHERE pr.pharmacy_id = %s
          AND pr.status      = 'pending'
        ORDER BY pr.created_at ASC;
    """, (pharm_id,))

    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(rows)


@pharmacy_queue_bp.route('/prescriptions/<int:prescription_id>/fulfill', methods=['POST'])
def fulfill_prescription(prescription_id):
    user_id = request.args.get('user_id', type=int)
    if not user_id:
        return jsonify(error="user_id is required"), 400

    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        # 1) lookup pharmacy_id
        pharm_id = _get_pharmacy_id_for_user(user_id, cursor)
        if pharm_id is None:
            return jsonify(error="No active pharmacy found for that user"), 404

        # 2) verify prescription belongs here & grab drug_id
        cursor.execute("""
            SELECT drug_id
              FROM prescriptions
             WHERE prescription_id = %s
               AND pharmacy_id     = %s
        """, (prescription_id, pharm_id))
        pres = cursor.fetchone()
        if not pres:
            return jsonify(error="Prescription not found or unauthorized"), 404
        drug_id = pres['drug_id']

        # 3) fetch human‐readable drug_name
        cursor.execute(
            "SELECT name FROM weight_loss_drugs WHERE drug_id = %s",
            (drug_id,)
        )
        row = cursor.fetchone()
        if not row:
            return jsonify(error=f"Drug id {drug_id} not found"), 404
        drug_name = row['name']

        # 4) check inventory for that drug at this pharmacy
        cursor.execute("""
            SELECT stock_quantity
              FROM pharmacy_inventory
             WHERE pharmacy_id = %s
               AND drug_name   = %s
        """, (pharm_id, drug_name))
        inv = cursor.fetchone()
        if not inv or inv['stock_quantity'] <= 0:
            return jsonify(error="Out of stock"), 400

        # 5) decrement inventory
        cursor.execute("""
            UPDATE pharmacy_inventory
               SET stock_quantity = stock_quantity - 1
             WHERE pharmacy_id = %s
               AND drug_name   = %s
        """, (pharm_id, drug_name))

        # 6) mark prescription as filled
        cursor.execute("""
            UPDATE prescriptions
               SET status = 'filled'
             WHERE prescription_id = %s
               AND pharmacy_id     = %s
        """, (prescription_id, pharm_id))

        conn.commit()
        return jsonify(message="Prescription marked as filled")

    except mysql.connector.Error as err:
        conn.rollback()
        print(f"[ERROR] fulfill_prescription exception: {err}", file=sys.stderr)
        return jsonify(error="Internal server error", detail=str(err)), 500

    finally:
        cursor.close()
        conn.close()
