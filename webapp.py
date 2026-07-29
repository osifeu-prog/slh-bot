from flask import Flask, jsonify, send_from_directory, request
import sqlite3, json, os

app = Flask(__name__, static_folder='web')
DB_NAME = "slh_empire.db"
CONFIG_FILE = "config.json"

def load_config():
    with open(CONFIG_FILE) as f:
        return json.load(f)

config = load_config()
ADMIN_ID = int(config.get("OWNER_ID",0))

@app.route("/")
def home():
    return send_from_directory('web', 'index.html')

@app.route("/dashboard")
def dash():
    return send_from_directory('web/dashboard', 'index.html')

@app.route("/api/status")
def status():
    conn=sqlite3.connect(DB_NAME)
    users=conn.cursor().execute("SELECT COUNT(*) FROM wallets").fetchone()[0]
    courses=conn.cursor().execute("SELECT COUNT(*) FROM academy_courses").fetchone()[0]
    conn.close()
    return jsonify({"users": users, "courses": courses, "status": "online", "admin_id": ADMIN_ID})

@app.route("/api/stats")
def stats():
    return status()

@app.route("/api/health")
def health():
    return jsonify({"status": "online"})

@app.route("/api/admin")
def admin_data():
    if request.args.get('id')!= str(ADMIN_ID):
        return jsonify({"error":"no auth"}), 403
    conn=sqlite3.connect(DB_NAME)
    users=conn.cursor().execute("SELECT user_id, wallet_balance FROM wallets").fetchall()
    commands = open("admin_menu.txt").read()
    conn.close()
    return jsonify({"users": users, "commands": commands})

@app.route("/api/exec", methods=["POST"])
def exec_cmd():
    if request.args.get('id')!= str(ADMIN_ID):
        return jsonify({"error":"no auth"}), 403
    cmd = request.json.get("command","")
    return jsonify({"result": f"✅ פקודה /{cmd} התקבלה. שולח לבוט..."})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
