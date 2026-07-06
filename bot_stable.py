import telebot
from telebot import types
import logging
import json
import os
from datetime import datetime

logging.basicConfig(level=logging.INFO)
bot = telebot.TeleBot(os.environ.get("BOT_TOKEN"))

# Load DB
def load_db():
    try:
        with open("state/db.json", "r") as f:
            return json.load(f)
    except:
        return {"users": {}, "agents": {}, "stakes": {}}

def save_db(db):
    with open("state/db.json", "w") as f:
        json.dump(db, f, indent=2)

@bot.message_handler(commands=['start'])
def start(m):
    db = load_db()
    uid = str(m.chat.id)
    name = db.get("users", {}).get(uid, {}).get("name", "אסף")
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton("🏛 אקדמיה", callback_data="academy")
    btn2 = types.InlineKeyboardButton("💰 השקעות", callback_data="invest")
    btn3 = types.InlineKeyboardButton("🔰 Staking", callback_data="stake")
    btn4 = types.InlineKeyboardButton("📊 PnL", callback_data="pnl")
    markup.add(btn1, btn2, btn3, btn4)
    bot.reply_to(m, f"ברוך הבא ל-SLH OS!\nנעים לראותך שוב, {name}!\nבחר:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    if call.data == "invest":
        bot.send_message(call.message.chat.id, "💰 בחר תקופה:\n1 חודש (4%)\n1 שנה (65%+)\n10 שנים (בונוס)\n\nשלח /stake_join <amount> USDT")
    elif call.data == "stake":
        bot.send_message(call.message.chat.id, "🔰 /stake_join <amount> USDT")
    elif call.data == "pnl":
        bot.send_message(call.message.chat.id, "📈 PnL: -1310$\nTrades: 36")
    elif call.data == "academy":
        bot.send_message(call.message.chat.id, "🏛 /course_slh")

print("✅ Unified SLH OS Bot started")
bot.infinity_polling()
