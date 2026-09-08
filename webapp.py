from flask import Flask, jsonify, send_from_directory, request
import json
from pathlib import Path

from core.telegram_webapp_auth import validate_init_data

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "state" / "db.json"

app = Flask(__name__)


def load_db():
    if not DB_PATH.exists():
        return {}
    with DB_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def authenticated_uid():
    """Return the Telegram UID authenticated by server-validated initData."""
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    try:
        return validate_init_data(init_data)["uid"]
    except (ValueError, RuntimeError):
        return None


def require_self(uid):
    authenticated = authenticated_uid()
    if authenticated is None:
        return jsonify({"error": "TELEGRAM_AUTH_REQUIRED"}), 401
    if str(uid) != authenticated:
        return jsonify({"error": "FORBIDDEN_USER_MISMATCH"}), 403
    return None


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
    denied = require_self(uid)
    if denied:
        return denied

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
    denied = require_self(uid)
    if denied:
        return denied

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


@app.route("/api/stats")
def stats():
    db = load_db()
    users = db.get("users", {})
    agents = db.get("agents", {})
    tasks = db.get("tasks", {})
    total_credits = 0

    if isinstance(users, dict):
        for user in users.values():
            if isinstance(user, dict):
                wallet = user.get("wallet", {})
                if isinstance(wallet, dict):
                    credits = wallet.get("credits", 0)
                    if isinstance(credits, (int, float)):
                        total_credits += credits

    return jsonify({
        "users": len(users) if isinstance(users, dict) else 0,
        "agents": len(agents) if isinstance(agents, dict) else 0,
        "tasks": len(tasks) if isinstance(tasks, dict) else 0,
        "credits": total_credits,
    })


@app.route("/api/leaderboard")
def api_leaderboard():
    try:
        from plugins.leaderboard import LeaderboardPlugin

        lb = LeaderboardPlugin(str(DB_PATH))
        top = lb.get_top(10)

        result = []

        for uid, data in top:
            result.append({
                "name": data.get("name", f"User{uid}"),
                "points": (data.get("gamification") or {}).get("points", 0)
            })

        return jsonify(result)

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500


@app.route("/api/onchain/status")
def onchain_status():
    from core.deposit_monitor import get_onchain_status
    return jsonify(get_onchain_status())


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=8080
    )
