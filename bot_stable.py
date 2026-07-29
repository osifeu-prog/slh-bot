import telebot
import sqlite3

TOKEN = "הכנס_כאן_את_הטוקן_שלך"
ADMIN_ID = 123456789
DB_NAME = "slh_empire.db"
bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=["start"])
def start(message):
    user_id = str(message.from_user.id)
    chat_id = message.chat.id
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO wallets VALUES (?,?,?)", (user_id, 0, chat_id))
    conn.commit()
    conn.close()
    bot.reply_to(message, "נרשמת ל-SLH Empire! /wallet ליתרה /buy לקנות")

@bot.message_handler(commands=["wallet"])
def wallet(message):
    user_id = str(message.from_user.id)
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT wallet_balance FROM wallets WHERE user_id=?", (user_id,))
    res = c.fetchone()
    conn.close()
    balance = res[0] if res else 0
    bot.reply_to(message, f"היתרה שלך: {balance} SLH")

@bot.message_handler(commands=["buy"])
def buy_handler(message):
    bot.reply_to(message, "לקניית SLH שלח לי כתובת BSC שלך\nחוזה: 0xACb0A09414CEA1C879c67bB7A877E4e19480f022\n1 USDT = 10 SLH")

@bot.message_handler(commands=["broadcast"])
def broadcast_handler(message):
    if message.from_user.id!= ADMIN_ID:
        bot.reply_to(message, "אין לך הרשאה")
        return
    text = message.text.replace("/broadcast ", "")
    if not text:
        bot.reply_to(message, "שימוש: /broadcast ההודעה שלך")
        return
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT chat_id FROM wallets WHERE chat_id IS NOT NULL")
    users = c.fetchall()
    conn.close()
    sent = 0
    for u in users:
        try:
            bot.send_message(u[0], f"📢 הודעה מ-SLH Empire:\n\n{text}")
            sent += 1
        except:
            pass
    bot.reply_to(message, f"נשלח ל-{sent} משתמשים")

bot.polling(none_stop=True)
