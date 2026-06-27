from flask import Flask, jsonify, request
from flask_cors import CORS
import json, os

app = Flask(__name__)
CORS(app)

DB_FILE = os.path.join(os.path.dirname(__file__), "../../db.json")

def load_db():
    try:
        with open(DB_FILE) as f:
            return json.load(f)
    except:
        return {"agents": {}, "tasks": [], "users": {}, "votes": {}}

def save_db(data):
    with open(DB_FILE, 'w') as f:
        json.dump(data, f, indent=2)

@app.route('/api/agents', methods=['GET'])
def get_agents():
    db = load_db()
    return jsonify(db.get('agents', {}))

@app.route('/api/agents', methods=['POST'])
def create_agent():
    data = request.json
    db = load_db()
    if 'agents' not in db:
        db['agents'] = {}
    agent_id = str(len(db['agents']) + 1)
    db['agents'][agent_id] = data
    save_db(db)
    return jsonify({'id': agent_id, 'agent': data}), 201

@app.route('/api/tasks', methods=['GET'])
def get_tasks():
    db = load_db()
    return jsonify(db.get('tasks', []))

@app.route('/api/tasks', methods=['POST'])
def create_task():
    data = request.json
    db = load_db()
    if 'tasks' not in db:
        db['tasks'] = []
    task_id = len(db['tasks'])
    task = {'id': task_id, **data, 'done': False}
    db['tasks'].append(task)
    save_db(db)
    return jsonify(task), 201

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'version': '2.0'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
