import telebot, sqlite3, logging
logging.basicConfig(level=logging.INFO)

TOKEN = "הכנס_כאן_את_הטוקן_שלך"
ADMIN_ID = 123456789 # << תחליף למספר מהשלב הקודם
DB_NAME = "slh_empire.db"
bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=["start","help"])
def start(message):
    user_id = str(message.from_user.id)
    chat_id = message.chat.id
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO wallets VALUES (?,?,?)", (user_id, 0, chat_id))
    conn.commit()
    conn.close()
    bot.reply_to(message, "ברוך הבא ל-SLH Empire! 🚀\n\nפקודות:\n/wallet - יתרה\n/buy - קנייה\n/referral - הזמנת חברים\n/admin - פאנל אדמין")

@bot.message_handler(commands=["wallet"])
def wallet(message):
    user_id = str(message.from_user.id)
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT wallet_balance FROM wallets WHERE user_id=?", (user_id,))
    res = c.fetchone()
    conn.close()
    bot.reply_to(message, f"💰 היתרה שלך: {res[0] if res else 0} SLH")

@bot.message_handler(commands=["buy"])
def buy(message):
    bot.reply_to(message, "1 USDT = 10 SLH\nשלח לי כתובת BSC ואני אשלח קישור תשלום")

@bot.message_handler(commands=["referral"])
def referral(message):
    bot_username = bot.get_me().username
    bot.reply_to(message, f"הזמן חברים וקבל 10 SLH:\nhttps://t.me/{bot_username}?start={message.from_user.id}")

@bot.message_handler(commands=["broadcast"])
def broadcast(message):
    if message.from_user.id!= ADMIN_ID: return bot.reply_to(message, "אין הרשאה")
    text = message.text.replace("/broadcast ", "")
    conn = sqlite3.connect(DB_NAME)
    users = conn.cursor().execute("SELECT chat_id FROM wallets WHERE chat_id IS NOT NULL").fetchall()
    conn.close()
    sent = 0
    for u in users:
        try: bot.send_message(u[0], f"📢 הודעה מ-SLH Empire:\n\n{text}"); sent+=1
        except: pass
    bot.reply_to(message, f"✅ נשלח ל-{sent} משתמשים")

@bot.message_handler(commands=["admin"])
def admin_panel(message):
    if message.from_user.id!= ADMIN_ID: return
    conn = sqlite3.connect(DB_NAME)
    count = conn.cursor().execute("SELECT COUNT(*) FROM wallets").fetchone()[0]
    conn.close()
    bot.reply_to(message, f"📊 פאנל אדמין SLH\nמשתמשים רשומים: {count}\nשימוש: /broadcast ההודעה")

bot.polling(none_stop=True)
