from flask import Blueprint, request, jsonify
import mysql.connector
from config import DB_CONFIG


payments_bp = Blueprint('payments', __name__, url_prefix='/api/pharmacy')


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


@payments_bp.route('/payments', methods=['GET'])
def get_pharmacy_payments():
    """
    Return fulfilled and unfulfilled payments for this pharmacy.
    Query:  ?user_id=<pharmacy_user_id>
    Response: {
      "fulfilled":   [ { payment_id, patient_name, amount, payment_date, ... }, … ],
      "unfulfilled": [ { … }, … ]
    }
    """
    user_id = request.args.get('user_id', type=int)
    if not user_id:
        return jsonify(error="user_id is required"), 400

    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)

    # resolve pharmacy_id from user
    pharm_id = _get_pharmacy_id_for_user(user_id, cursor)
    if pharm_id is None:
        cursor.close()
        conn.close()
        return jsonify(error="No active pharmacy found for that user"), 404

    # fetch all payments
    cursor.execute("""
      SELECT
        p.payment_id,
        CONCAT(pt.first_name, ' ', pt.last_name) AS patient_name,
        p.amount,
        p.is_fulfilled,
        p.payment_date
      FROM payments_pharmacy p
      JOIN patients pt ON p.patient_id = pt.patient_id
      WHERE p.pharmacy_id = %s
      ORDER BY p.payment_date DESC;
    """, (pharm_id,))
    payments = cursor.fetchall()

    cursor.close()
    conn.close()

    # split into two lists
    fulfilled = [row for row in payments if row['is_fulfilled']]
    unfulfilled = [row for row in payments if not row['is_fulfilled']]

    return jsonify({"fulfilled": fulfilled, "unfulfilled": unfulfilled}), 200
