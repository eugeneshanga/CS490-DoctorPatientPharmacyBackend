from flask import Blueprint, jsonify, request
import mysql.connector
from config import DB_CONFIG

pharmacy_prescriptions_bp = Blueprint('pharmacy_prescriptions', __name__)


def _get_pharmacy_id_for_user(user_id, cursor):
    cursor.execute(
        "SELECT pharmacy_id FROM pharmacies WHERE user_id = %s AND is_active = TRUE LIMIT 1",
        (user_id,)
    )
    row = cursor.fetchone()
    return row['pharmacy_id'] if row else None


@pharmacy_prescriptions_bp.route('/api/pharmacy/prescriptions', methods=['GET'])
def get_prescriptions():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        search = request.args.get('search')

        base_query = """
        SELECT
            p.prescription_id,
            CONCAT(pa.first_name, ' ', pa.last_name) AS patient_name,
            p.medication_name,
            p.dosage,
            p.status,
            p.instructions,
            p.created_at
        FROM prescriptions p
        JOIN patients pa ON p.patient_id = pa.patient_id
        """

        if search:
            if search.isdigit():
                base_query += " WHERE p.prescription_id = %s"
                cursor.execute(base_query, (int(search),))
            else:
                base_query += " WHERE p.medication_name LIKE %s"
                cursor.execute(base_query, (f"%{search}%",))
        else:
            cursor.execute(base_query)

        prescriptions = cursor.fetchall()
        cursor.close()
        conn.close()

        return jsonify(prescriptions)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@pharmacy_prescriptions_bp.route('/api/pharmacy/prescriptions/<int:prescription_id>', methods=['GET'])
def get_prescription_by_id(prescription_id):
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        query = """
        SELECT
            p.prescription_id,
            CONCAT(pa.first_name, ' ', pa.last_name) AS patient_name,
            p.medication_name,
            p.dosage,
            p.instructions,
            p.status,
            p.created_at
        FROM prescriptions p
        JOIN patients pa ON p.patient_id = pa.patient_id
        WHERE p.prescription_id = %s
        """

        cursor.execute(query, (prescription_id,))
        prescription = cursor.fetchone()

        cursor.close()
        conn.close()

        if prescription:
            return jsonify(prescription)
        else:
            return jsonify({"error": "Prescription not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@pharmacy_prescriptions_bp.route('/api/pharmacy/requests', methods=['GET'])
def get_prescription_requests():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        pharmacy_id = request.args.get('pharmacy_id')
        print("Received pharmacy_id:", pharmacy_id)
        query = """
        SELECT
            p.prescription_id,
            CONCAT(pa.first_name, ' ', pa.last_name) AS patient_name,
            p.medication_name,
            p.dosage,
            p.status,
            pi.stock_quantity,
            CASE
                WHEN pi.stock_quantity IS NULL OR pi.stock_quantity <= 0 THEN TRUE
                ELSE FALSE
            END AS inventory_conflict
        FROM prescriptions p
        JOIN patients pa ON p.patient_id = pa.patient_id
        LEFT JOIN pharmacy_inventory pi ON lower(trim(p.medication_name)) = lower(trim(pi.drug_name))
            AND p.pharmacy_id = pi.pharmacy_id
        WHERE p.status = 'pending' AND p.pharmacy_id = %s
        """

        cursor.execute(query, (pharmacy_id,))
        results = cursor.fetchall()

        cursor.close()
        conn.close()

        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@pharmacy_prescriptions_bp.route('/api/pharmacy/logs', methods=['GET'])
def view_past_transactions():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        search = request.args.get('search')

        query = """
        SELECT
            l.prescription_id,
            CONCAT(p.first_name, ' ', p.last_name) AS patient_name,
            r.medication_name,
            l.amount_billed,
            l.timestamp
        FROM pharmacy_logs l
        JOIN prescriptions r ON l.prescription_id = r.prescription_id
        JOIN patients p ON l.patient_id = p.patient_id
        """

        if search:
            query += " WHERE r.medication_name LIKE %s OR CONCAT(p.first_name, ' ', p.last_name) LIKE %s"
            cursor.execute(query + " ORDER BY p.last_name ASC, p.first_name ASC", (f"%{search}%", f"%{search}%"))
        else:
            cursor.execute(query + " ORDER BY p.last_name ASC, p.first_name ASC")

        results = cursor.fetchall()
        cursor.close()
        conn.close()

        if results:
            return jsonify(results)
        else:
            return jsonify({"message": "No transactions found."}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@pharmacy_prescriptions_bp.route('/api/pharmacy/inventory/add', methods=['POST'])
def add_inventory_item():
    if not request.is_json:
        return jsonify(error="Request body must be JSON"), 400

    data = request.get_json()
    user_id = data.get('user_id')
    drug_name = data.get('drug_name')
    stock_quantity = data.get('stock_quantity')

    if not user_id or not drug_name or stock_quantity is None:
        return jsonify(error="Missing required fields"), 400

    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # 1) Resolve pharmacy_id
        pharm_id = _get_pharmacy_id_for_user(user_id, cursor)
        if pharm_id is None:
            return jsonify(error="Pharmacy not found for this user"), 404

        # 2) See if an entry already exists
        cursor.execute("""
            SELECT stock_quantity
              FROM pharmacy_inventory
             WHERE pharmacy_id = %s
               AND drug_name   = %s
        """, (pharm_id, drug_name))
        existing = cursor.fetchone()

        if existing:
            # 3a) Update
            new_qty = existing['stock_quantity'] + int(stock_quantity)
            cursor.execute("""
                UPDATE pharmacy_inventory
                   SET stock_quantity = %s
                 WHERE pharmacy_id   = %s
                   AND drug_name     = %s
            """, (new_qty, pharm_id, drug_name))
        else:
            # 3b) Insert
            cursor.execute("""
                INSERT INTO pharmacy_inventory
                    (pharmacy_id, drug_name, stock_quantity)
                VALUES (%s, %s, %s)
            """, (pharm_id, drug_name, int(stock_quantity)))

        conn.commit()
        return jsonify(message="Inventory item added successfully"), 201

    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify(error="Internal server error", detail=str(err)), 500

    finally:
        cursor.close()
        conn.close()


@pharmacy_prescriptions_bp.route('/api/pharmacy/inventory', methods=['GET'])
def get_inventory():
    user_id = request.args.get('user_id', type=int)
    if not user_id:
        return jsonify(error="user_id is required"), 400

    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # 1) Resolve pharmacy_id
        pharm_id = _get_pharmacy_id_for_user(user_id, cursor)
        if pharm_id is None:
            return jsonify(error="Pharmacy not found for this user"), 404

        # 2) Fetch inventory
        cursor.execute("""
            SELECT drug_name, stock_quantity
              FROM pharmacy_inventory
             WHERE pharmacy_id = %s
        """, (pharm_id,))
        inventory = cursor.fetchall()

        return jsonify(inventory), 200

    except mysql.connector.Error as err:
        return jsonify(error="Internal server error", detail=str(err)), 500

    finally:
        cursor.close()
        conn.close()


@pharmacy_prescriptions_bp.route('/api/pharmacy/getPharmacyId', methods=['GET'])
def get_pharmacy_id():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"error": "Missing user_id"}), 400

    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT pharmacy_id FROM pharmacies WHERE user_id = %s", (user_id,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()

        if result:
            return jsonify(result)
        else:
            return jsonify({"error": "Pharmacy not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500
