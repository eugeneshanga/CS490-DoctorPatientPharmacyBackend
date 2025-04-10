from flask import Flask, jsonify
from flask_cors import CORS  # Allow cross-origin requests

app = Flask(__name__)
CORS(app)  # Enable CORS so that your React app can call this API

@app.route('/api/hello', methods=['GET'])
def hello():
    return jsonify(message="Hello World!")

if __name__ == '__main__':
    app.run(debug=True)
