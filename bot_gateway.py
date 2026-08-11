from dotenv import load_dotenv
load_dotenv('.env')
import os, json, time, threading, traceback, sys
from pathlib import Path
import telebot
from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS

app = Flask(__name__)

from core.control_center_api import register_control_center
register_control_center(app)

# SLH Mini App / Market API
try:
    from webapp import app as webapp_app
    for rule in webapp_app.url_map.iter_rules():
        if rule.rule == '/static/<path:filename>':
            continue
        if rule.rule == '/health':
            continue
        view = webapp_app.view_functions[rule.endpoint]
        app.add_url_rule(
            rule.rule,
            endpoint='webapp_' + rule.endpoint,
            view_func=view,
            methods=[m for m in rule.methods if m not in ('HEAD', 'OPTIONS')]
        )
    print('[SLH] WebApp routes mounted into gateway')
except Exception as e:
    print(f'[SLH] WebApp route mount failed: {e}')


@app.route('/health')
def health():
    return jsonify({"status": "ok", "service": "SLH OS Gateway"}), 200

@app.route('/api/agents')
def api_agents():
    try:
        from core.agent_registry import STORE
        agents = STORE.get_all()
        result = {aid: {"name": a.get("name"), "state": a.get("state")} for aid, a in agents.items()}
        return jsonify({"total": len(agents), "agents": result}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/devices')
def api_devices():
    try:
        import json
        with open("state/devices.json", encoding="utf-8") as f:
            data = json.load(f)
        return jsonify(data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/')
def index():
    return 'SLH OS Gateway', 200

@app.route('/dashboard')
def dashboard():
    return send_from_directory('web/dashboard_v2', 'index.html')

@app.route('/app.js')
def dashboard_app_js():
    return send_from_directory('web/dashboard_v2', 'app.js')

@app.route('/style.css')
def dashboard_style_css():
    return send_from_directory('web/dashboard_v2', 'style.css')

@app.route('/branding/<path:filename>')
def dashboard_branding(filename):
    return send_from_directory('branding', filename)
@app.route('/api/health')
def api_health():
    return jsonify({
        "status": "ok",
        "service": "SLH OS Dashboard API"
    }), 200

@app.route('/api/logs')
def api_logs():
    try:
        n = request.args.get('n', 50, type=int)
        log_file = Path("logs/bot_startup.log")

        if not log_file.exists():
            return jsonify([]), 200

        with log_file.open("r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        return jsonify(lines[-n:]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
@app.route('/api/stats')
def api_stats():
    try:
        with open("state/db.json", encoding="utf-8") as f:
            db = json.load(f)
        users = len(db.get("users", {}))
        tasks = len(db.get("tasks", {}))
        agents = len(db.get("agents", {}))
        owner = db.get("users", {}).get("8789977826", {})
        credits = owner.get("wallet", {}).get("credits", 0)
        return jsonify({
            "users": users,
            "tasks": tasks,
            "agents": agents,
            "credits": credits
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def run_flask():
    port = int(os.getenv('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

LOG_FILE = Path("logs/bot_startup.log")
LOG_FILE.parent.mkdir(exist_ok=True)

def log(msg):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")
    print(msg)

try:
    from handlers.loader import load_handlers
    log("import loader OK")
except Exception as e:
    log(f"FATAL: import loader failed: {traceback.format_exc()}")
    sys.exit(1)

STATE_DIR = Path("state")
STATE_DIR.mkdir(exist_ok=True)

def load_bots():
    if (STATE_DIR / "bots.json").exists():
        return json.load(open(STATE_DIR / "bots.json", encoding="utf-8"))
    return {"Me_ad_main": os.getenv("BOT_TOKEN")}

def run_bot(bot):
    while True:
        try:
            log("Starting polling...")
            bot.infinity_polling(timeout=60, long_polling_timeout=60, skip_pending=True)
        except Exception as e:
            log(f"Polling crashed: {e}")
            time.sleep(10)

if __name__ == "__main__":
    log("=== BOT + API GATEWAY STARTUP ===")
    log(f"Python: {sys.executable} {sys.version}")
    log(f"RUN_BOT: {os.getenv('RUN_BOT')}")
    log(f"BOT_TOKEN: {'PRESENT' if os.getenv('BOT_TOKEN') else 'MISSING'}")

    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    log("Flask API gateway started")

    if os.getenv("RUN_BOT") != "1":
        log("RUN_BOT != 1, sleeping...")
        while True:
            time.sleep(3600)

    data = load_bots()
    for bot_name, token in data.items():
        if not token:
            log(f"Skipping {bot_name}: no token")
            continue
        bot = telebot.TeleBot(token, parse_mode=None)
        # Removed cp862 fix ׳³ג€™׳’ג€ֲ¬׳’ג‚¬ֲ using native UTF-8
        # patched_process_new_updates disabled
        load_handlers(bot, {"bot_name": bot_name})
        log(f"[OK] Bot {bot_name} started")
        threading.Thread(target=run_bot, args=(bot,), daemon=True).start()
    log("[SLH] All bots + API running. Waiting...")
    while True:
        time.sleep(1)
# deploy-marker 20260808_113100



