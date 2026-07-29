import telebot, sqlite3, logging, os, sys
logging.basicConfig(level=logging.INFO)

DB_NAME = "slh_empire.db"
CONFIG_FILE = "config.txt"

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            lines = f.read().splitlines()
            return lines[0], int(lines[1])
    return "", 0

TOKEN, ADMIN_ID = load_config()
bot = telebot.TeleBot(TOKEN) if TOKEN else None

def save_config(token, admin):
    with open(CONFIG_FILE, "w") as f:
        f.write(f"{token}\n{admin}")

if bot:
    @bot.message_handler(commands=["settoken"])
    def set_token(message):
        global TOKEN, bot
        if message.from_user.id!= ADMIN_ID and ADMIN_ID!= 0: return bot.reply_to(message, "אין הרשאה")
        new_token = message.text.replace("/settoken ", "")
        save_config(new_token, ADMIN_ID)
        bot.reply_to(message, "✅ טוקן עודכן! שלח /restart")

    @bot.message_handler(commands=["setadmin"])
    def set_admin(message):
        global ADMIN_ID
        if message.from_user.id!= ADMIN_ID and ADMIN_ID!= 0: return
        new_admin = int(message.text.replace("/setadmin ", ""))
        save_config(TOKEN, new_admin)
        bot.reply_to(message, f"✅ אדמין עודכן ל: {new_admin}")

    @bot.message_handler(commands=["restart"])
    def restart(message):
        if message.from_user.id!= ADMIN_ID: return
        bot.reply_to(message, "מפעיל מחדש...")
        os.execv(sys.executable, ['python3'] + sys.argv)

    @bot.message_handler(commands=["start","help"])
    def start(message):
        user_id = str(message.from_user.id)
        chat_id = message.chat.id
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO wallets VALUES (?,?,?)", (user_id, 0, chat_id))
        conn.commit()
        conn.close()
        bot.reply_to(message, "ברוך הבא ל-SLH Empire! 🚀\n\n/wallet - יתרה\n/buy - קנייה\n/referral - הזמנה\n/admin - פאנל\nאדמין: /settoken /setadmin")

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
        bot.reply_to(message, "1 USDT = 10 SLH\nשלח כתובת BSC")

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
        bot.reply_to(message, f"📊 פאנל אדמין SLH\nמשתמשים רשומים: {count}\nפקודות: /settoken /setadmin /broadcast")

if __name__ == "__main__":
    if TOKEN:
        bot.polling(none_stop=True)
    else:
        print("צור קובץ config.txt עם טוקן ו-ADMIN")
