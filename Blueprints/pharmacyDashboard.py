from flask import Blueprint, jsonify, request
import mysql.connector
from config import DB_CONFIG

# Create a blueprint for the pharmacist dashboard endpoints
pharmacist_dashboard_bp = Blueprint('pharmacist_dashboard', __name__, url_prefix='/api/pharmacist-dashboard')

@pharmacist_dashboard_bp.route('/details', methods=['GET'])
def get_pharmacist_details():
    """
    Endpoint to retrieve pharmacist details for a given user_id.
    It expects a query parameter 'user_id' and returns details such as pharmacist_id,
    first_name, last_name, and any other columns as needed.
    """
    user_id = request.args.get('user_id', type=int)
    if not user_id:
        return jsonify({"error": "user_id query parameter is required"}), 400

    try:
        # Establish a connection to the database
        connection = mysql.connector.connect(**DB_CONFIG)
        cursor = connection.cursor(dictionary=True)

        # Query the pharmacists table using the provided user_id
        # Adjust the query if your table/column names differ.
        cursor.execute(
            "SELECT pharmacist_id, first_name, last_name FROM pharmacists WHERE user_id = %s",
            (user_id,)
        )
        pharmacist = cursor.fetchone()
        if not pharmacist:
            return jsonify({"error": "Pharmacist not found for given user_id"}), 404

        cursor.close()
        connection.close()

        return jsonify({"pharmacist": pharmacist}), 200

    except mysql.connector.Error as err:
        return jsonify({"error": str(err)}), 500
