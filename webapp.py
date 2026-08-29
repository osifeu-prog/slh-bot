from flask import Flask, jsonify, send_from_directory
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "state" / "db.json"

app = Flask(__name__)

def load_db():
    if not DB_PATH.exists():
        return {}
    with DB_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)

@app.route("/health")
def health():
    return "OK", 200

@app.route("/market")
def market():
    return jsonify({
        "status": "SLH Market UP",
        "time": "2026-08-11"
    }), 200

@app.route("/mini-app")
def mini_app():
    resp = send_from_directory(BASE_DIR, "mini_app.html")
    resp.headers["Content-Type"] = "text/html; charset=utf-8"
    return resp

@app.route("/api/wallet/<uid>")
def get_wallet(uid):
    db = load_db()
    user = db.get("users", {}).get(str(uid), {})
    wallet = user.get("wallet", {})

    return jsonify({
        "name": user.get("name", str(uid)),
        "credits": wallet.get("credits", 0),
        "staked": wallet.get("staked", 0),
        "token_balance": wallet.get("token_balance", 0),
        "ton_wallet": user.get("ton_wallet")
    })

@app.route("/api/tasks/<uid>")
def get_tasks(uid):
    db = load_db()
    tasks = db.get("tasks", {})

    result = []

    for tid, task in tasks.items():
        if str(task.get('owner_id', '')) not in ('', str(uid)):
            continue
        done_by = task.get("done_by", [])

        result.append({
            "id": tid,
            "title": task.get("title", "?"),
            "reward": task.get("reward", 0),
            "status": (
                "done"
                if str(uid) in [str(x) for x in done_by]
                else task.get("status", "open")
            ),
            "agent": task.get("agent", "unassigned")
        })

    return jsonify(result)

@app.route("/api/leaderboard")
def api_leaderboard():
    try:
        from plugins.leaderboard import LeaderboardPlugin

        lb = LeaderboardPlugin(str(DB_PATH))
        top = lb.get_top(10)

        result = []

        for uid, data in top:
            wallet = data.get("wallet", {})

            result.append({
                "uid": str(uid),
                "name": data.get("name", f"User{uid}"),
                "credits": wallet.get("credits", 0)
            })

        return jsonify(result)

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=8080
    )


@app.route("/api/onchain/status")
def onchain_status():
    from core.deposit_monitor import get_onchain_status
    return jsonify(get_onchain_status())

