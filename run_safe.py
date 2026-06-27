import json
import telebot

cfg = json.load(open("config.json"))
token = cfg.get("BOT_TOKEN")

if ":" not in token:
    print("[FATAL] Invalid Telegram token")
    exit(1)

bot = telebot.TeleBot(token)

print("BOT STARTED SAFE MODE")

@bot.message_handler(commands=['start'])
def start(m):
    bot.reply_to(m, "System alive")

bot.polling()
