import json
import os
import time
import telebot

LOCK = "slh_bot.lock"

if os.path.exists(LOCK):
    print("❌ already running (lock exists)")
    exit()

open(LOCK, "w").write(str(os.getpid()))

def cleanup():
    try:
        os.remove(LOCK)
    except:
        pass

try:
    token = json.load(open("config.json"))["BOT_TOKEN"]
    bot = telebot.TeleBot(token)

    @bot.message_handler(commands=['start'])
    def start(m):
        bot.reply_to(m, "🚀 SLH CLEAN BOT ONLINE")

    @bot.message_handler(commands=['status'])
    def status(m):
        bot.reply_to(m, "🟢 OK")

    print("🚀 BOT RUNNING (SAFE MODE)")

    while True:
        try:
            bot.polling(
                timeout=30,
                long_polling_timeout=10,
                skip_pending=True
            )
        except Exception as e:
            print("⚠️ restart:", e)
            time.sleep(5)

finally:
    cleanup()
