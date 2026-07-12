import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from flask import Flask, jsonify, request
from flask_cors import CORS
import json, os, time

app = Flask(__name__)
CORS(app)

DB_FILE = os.path.join(os.path.dirname(__file__), "../../state/db.json")

def load_db():
    try:
        with open(DB_FILE) as f:
            return json.load(f)
    except:
        return {"agents": {}, "tasks": [], "users": {}, "votes": {}}

def save_db(data):
    with open(DB_FILE, 'w') as f:
        json.dump(data, f, indent=2)

# --- Agents ---
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

# --- Tasks ---
@app.route('/api/tasks', methods=['GET'])
def get_tasks():
    db = load_db()
    tasks = db.get('tasks', [])
    if not isinstance(tasks, list):
        tasks = []
    return jsonify(tasks)

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

# --- Logs ---
@app.route('/api/logs', methods=['GET'])
def get_logs():
    n = request.args.get('n', 50, type=int)
    log_file = os.path.join(os.path.dirname(__file__), "../../bot.log")
    if not os.path.exists(log_file):
        return jsonify([])
    with open(log_file) as f:
        lines = f.readlines()
    return jsonify(lines[-n:])

# --- Stats ---
@app.route('/api/stats', methods=['GET'])
def get_stats():
    db = load_db()
    log_file = os.path.join(os.path.dirname(__file__), "../../bot.log")
    log_size = os.path.getsize(log_file) if os.path.exists(log_file) else 0
    return jsonify({
        "users": len(db.get("users", {})),
        "tasks": len(db.get("tasks", [])),
        "agents": len(db.get("agents", {})),
        "votes": db.get("votes", {}),
        "log_size_bytes": log_size,
        "version": "2.0"
    })

# --- Health ---
@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'version': '2.0'})



# ── Subscription endpoints ──────────────────────────
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

sys.path.insert(0, '/data/data/com.termux/files/home/slh_clean')
from subscriptions import load_subscriptions, get_user_plan, PLANS
import time as _time

@app.route('/api/subscriptions')
def api_all_subscriptions():
    return jsonify(load_subscriptions())

@app.route('/api/subscriptions/me')
def api_my_plan():
    user_id = request.args.get('user_id', '0')
    plan = get_user_plan(user_id)
    return jsonify({'plan': plan, 'info': PLANS.get(plan, {})})

@app.route('/api/subscriptions/set', methods=['POST'])
def api_set_plan():
    data = request.json or {}
    plan = data.get('plan', 'free')
    user_id = str(data.get('user_id', '0'))
    subs = load_subscriptions()
    subs[user_id] = {'plan': plan, 'since': _time.strftime('%Y-%m-%d')}
    import json
    with open('subscriptions.json', 'w') as f:
        json.dump(subs, f, indent=2)
    return jsonify({'ok': True})






@app.route("/branding/<path:filename>")
def branding(filename):
    from flask import send_from_directory
    return send_from_directory("/app/branding", filename)

@app.route("/dashboard")
def dashboard():
    from flask import send_file
    return send_file("/app/web/dashboard_v2/index.html")




@app.route("/dashboard-v2")
def dashboard_v2():
    from flask import send_file
    return send_file("/app/web/dashboard/index.html")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))

# --- Auth ---
API_KEY = os.getenv("SLH_API_KEY", "slh-secret-key")

@app.before_request
def check_auth():
    if request.endpoint not in ('health', 'get_agents', 'get_tasks', 'get_stats', 'get_logs', 'get_subscriptions', 'get_my_plan'):
        key = request.headers.get('X-API-Key', '')
        if key != API_KEY:
            return jsonify({"error": "Unauthorized"}), 401
