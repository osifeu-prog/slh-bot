import os, json, time, threading, traceback, sys
from pathlib import Path
import telebot
from flask import Flask, jsonify

app = Flask(__name__)

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
    log(f"BOT_TOKEN: {os.getenv('BOT_TOKEN')[:15]}...")

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
# FIX: telebot misinterprets UTF-8 bytes as cp862
original_process_new_updates = bot.process_new_updates
def patched_process_new_updates(updates):
    for update in updates:
        if update.message and update.message.text:
            try:
                update.message.text = update.message.text.encode('cp862').decode('utf-8')
            except (UnicodeError, UnicodeDecodeError, UnicodeEncodeError):
                pass
    return original_process_new_updates(updates)
bot.process_new_updates = patched_process_new_updates
        load_handlers(bot, {"bot_name": bot_name})
        log(f"[OK] Bot {bot_name} started")
        threading.Thread(target=run_bot, args=(bot,), daemon=True).start()
    log("[SLH] All bots + API running. Waiting...")
    while True:
        time.sleep(1)


# deploy-marker 20260808_113100

