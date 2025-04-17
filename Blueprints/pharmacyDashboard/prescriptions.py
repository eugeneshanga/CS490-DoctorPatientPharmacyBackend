from flask import Blueprint, jsonify, request
import mysql.connector
from config import DB_CONFIG

pharmacy_prescriptions_bp = Blueprint('pharmacy_prescriptions', __name__)

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
        LEFT JOIN pharmacy_inventory pi ON p.medication_name = pi.drug_name 
            AND p.pharmacy_id = pi.pharmacy_id
        WHERE p.status = 'pending'
        """

        cursor.execute(query)
        results = cursor.fetchall()

        cursor.close()
        conn.close()

        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@pharmacy_prescriptions_bp.route('/api/pharmacy/prescriptions/<int:prescription_id>/fulfill', methods=['POST'])
def fulfill_prescription(prescription_id):
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT p.*, pa.patient_id
            FROM prescriptions p
            JOIN patients pa ON p.patient_id = pa.patient_id
            WHERE p.prescription_id = %s AND p.status = 'pending'
        """, (prescription_id,))
        prescription = cursor.fetchone()

        if not prescription:
            return jsonify({"error": "Prescription not found or already fulfilled"}), 404

        cursor.execute("""
            SELECT * FROM pharmacy_inventory
            WHERE pharmacy_id = %s AND drug_name = %s
        """, (prescription['pharmacy_id'], prescription['medication_name']))
        inventory = cursor.fetchone()

        if not inventory or inventory['stock_quantity'] <= 0:
            return jsonify({"error": "Inventory conflict: medication not available"}), 409

        cursor.execute("""
            UPDATE prescriptions
            SET status = 'dispensed'
            WHERE prescription_id = %s
        """, (prescription_id,))

        cursor.execute("""
            UPDATE pharmacy_inventory
            SET stock_quantity = stock_quantity - 1
            WHERE inventory_id = %s
        """, (inventory['inventory_id'],))

        cursor.execute("""
            INSERT INTO pharmacy_logs (prescription_id, pharmacy_id, patient_id, amount_billed)
            VALUES (%s, %s, %s, %s)
        """, (
            prescription_id,
            prescription['pharmacy_id'],
            prescription['patient_id'],
            49.99
        ))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"message": "Prescription fulfilled and patient billed."}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
