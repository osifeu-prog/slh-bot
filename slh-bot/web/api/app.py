from flask import Flask, jsonify
import json, os

app = Flask(__name__)
DB_PATH = "/app/state/db.json"

@app.route("/")
def dashboard():
    return "<h1>SLH Dashboard v1.0</h1><p>Online</p><a href='/api/status'>API Status</a>"

@app.route("/api/status")
def status():
    try:
        d = json.load(open(DB_PATH)) if os.path.exists(DB_PATH) else {"devices":{}, "tasks":{}}
        return jsonify({"status": "ok", "devices": len(d.get("devices",{})), "tasks": len(d.get("tasks",{}))})
    except:
        return jsonify({"status": "error", "devices": 0, "tasks": 0})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
