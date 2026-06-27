from flask import Flask, jsonify, request
from flask_cors import CORS
import json, os

app = Flask(__name__)
CORS(app)

DB_FILE = os.path.join(os.path.dirname(__file__), "../../db.json")

def load_db():
    if not os.path.exists(DB_FILE):
        return {}
    with open(DB_FILE) as f:
        return json.load(f)

@app.route('/api/agents', methods=['GET'])
def get_agents():
    db = load_db()
    return jsonify(db.get('agents', {}))

@app.route('/api/tasks', methods=['GET'])
def get_tasks():
    db = load_db()
    return jsonify(db.get('tasks', []))

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'version': '2.0'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
