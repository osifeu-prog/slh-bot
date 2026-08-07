import os, json, time, threading
from pathlib import Path
import telebot
from handlers.loader import load_handlers

STATE_DIR = Path("state")
STATE_DIR.mkdir(exist_ok=True)
BOTS_FILE = STATE_DIR / "bots.json"

def load_bots():
    if BOTS_FILE.exists():
        return json.load(open(BOTS_FILE, encoding="utf-8"))
    return {"Me_ad_main": os.getenv("BOT_TOKEN")}

def run_bot(bot):
    while True:
        try:
            print("[SLH] Starting polling...")
            bot.infinity_polling(timeout=60, long_polling_timeout=60, skip_pending=True)
        except Exception as e:
            print(f"[SLH] Polling crashed: {e}")
            time.sleep(10)

if __name__ == "__main__":
    if os.getenv("RUN_BOT") != "1":
        print("RUN_BOT not set - skipping bot startup (web service)")
        while True:
            time.sleep(3600)
    data = load_bots()
    for bot_name, token in data.items():
        if not token:
            continue
        bot = telebot.TeleBot(token, parse_mode=None)
        load_handlers(bot, {"bot_name": bot_name})
        print(f"[OK] Bot {bot_name} started")
        threading.Thread(target=run_bot, args=(bot,), daemon=True).start()
    print("[SLH] All bots running. Waiting...")
    while True:
        time.sleep(1)
