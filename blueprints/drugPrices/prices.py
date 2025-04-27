from flask import Blueprint, jsonify, request
import mysql.connector
from config import DB_CONFIG

prices_bp = Blueprint('prices', __name__, url_prefix='/api/prices')

def _get_pharmacy_id_for_user(user_id, cursor):
    cursor.execute(
        "SELECT pharmacy_id FROM pharmacies WHERE user_id = %s AND is_active = TRUE LIMIT 1",
        (user_id,)
    )
    row = cursor.fetchone()
    return row['pharmacy_id'] if row else None

@prices_bp.route('/current-prices', methods=['GET'])
def get_prices():
    user_id = request.args.get('user_id', type=int)
    if not user_id:
        return jsonify(error="user_id is required"), 400

    conn   = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)

    # map to pharmacy_id
    pharm_id = _get_pharmacy_id_for_user(user_id, cursor)
    if pharm_id is None:
        return jsonify(error="No active pharmacy"), 404

    cursor.execute("""
      SELECT p.drug_id, d.name, d.description, p.price
      FROM pharmacy_drug_prices p
      JOIN weight_loss_drugs d ON p.drug_id = d.drug_id
      WHERE p.pharmacy_id = %s
      ORDER BY p.drug_id
    """, (pharm_id,))
    rows = cursor.fetchall()

    cursor.close()
    conn.close()
    return jsonify(rows), 200


@prices_bp.route('/update', methods=['PATCH'])
def update_price():
    data = request.get_json(force=True)
    user_id = data.get('user_id')
    drug_id = data.get('drug_id')
    price   = data.get('price')

    if not all([user_id, drug_id, price is not None]):
        return jsonify(error="user_id, drug_id, and price are required"), 400

    conn   = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()

    pharm_id = _get_pharmacy_id_for_user(user_id, cursor)
    if pharm_id is None:
        return jsonify(error="No active pharmacy"), 404

    cursor.execute("""
      UPDATE pharmacy_drug_prices
         SET price = %s
       WHERE pharmacy_id = %s
         AND drug_id     = %s
    """, (price, pharm_id, drug_id))
    if cursor.rowcount == 0:
        # If row doesn’t exist yet, insert it
        cursor.execute("""
          INSERT INTO pharmacy_drug_prices (pharmacy_id, drug_id, price)
          VALUES (%s, %s, %s)
        """, (pharm_id, drug_id, price))

    conn.commit()
    cursor.close()
    conn.close()
    return jsonify(message="Price updated"), 200

