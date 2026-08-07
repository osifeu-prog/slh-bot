import os, json, time, threading, traceback, sys
from pathlib import Path
import telebot

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
    log("=== BOT STARTUP ===")
    log(f"Python: {sys.executable} {sys.version}")
    log(f"RUN_BOT: {os.getenv('RUN_BOT')}")
    log(f"BOT_TOKEN: {os.getenv('BOT_TOKEN')[:15]}...")

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
        load_handlers(bot, {"bot_name": bot_name})
        log(f"[OK] Bot {bot_name} started")
        threading.Thread(target=run_bot, args=(bot,), daemon=True).start()
    log("[SLH] All bots running. Waiting...")
    while True:
        time.sleep(1)
