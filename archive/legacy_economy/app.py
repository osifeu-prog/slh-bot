from flask import Flask, jsonify, send_from_directory
import telebot, sqlite3, logging, os
logging.basicConfig(level=logging.INFO)

app = Flask(__name__, static_folder='web')
DB_NAME = "slh_empire.db"
CONFIG_FILE = "config.txt"
LOGO = "███████╗██╗ ██╗ ██╗\n██╔════╝██║ ██║ ██║\n███████╗██║ ███████║\n╚════██║██║ ██╔══██║\n███████║███████╗██║ ██║\n╚══════╝╚══════╝╚═╝ ╚═╝\n\nSLH SYSTEM"
SIGN = "\n\n---\nSLH Empire | 0xACb0A09414CEA1C879c67bB7A877E4e19480f022"

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            lines = f.read().splitlines()
            if len(lines) >= 2 and ":" in lines[0]: return lines[0], int(lines[1])
    return "", 0

TOKEN, ADMIN_ID = load_config()
bot = telebot.TeleBot(TOKEN) if TOKEN else None

if bot:
    @bot.message_handler(commands=["start"])
    def start(m):
        uid=str(m.from_user.id); cid=m.chat.id
        conn=sqlite3.connect(DB_NAME); c=conn.cursor()
        c.execute("INSERT OR IGNORE INTO wallets VALUES (?,?,?)", (uid,0,cid)); conn.commit(); conn.close()
        bot.reply_to(m, f"{LOGO}\nברוך הבא! /wallet /admin" + SIGN)

    @bot.message_handler(commands=["wallet"])
    def wallet(m):
        uid=str(m.from_user.id)
        conn=sqlite3.connect(DB_NAME); c=conn.cursor()
        c.execute("SELECT wallet_balance FROM wallets WHERE user_id=?", (uid,)); res=c.fetchone(); conn.close()
        bot.reply_to(m, f"{LOGO}\n💰 יתרה: {res[0] if res else 0} SLH" + SIGN)

    @bot.message_handler(commands=["admin"])
    def admin(m):
        if m.from_user.id!=ADMIN_ID: return
        conn=sqlite3.connect(DB_NAME); count=conn.cursor().execute("SELECT COUNT(*) FROM wallets").fetchone()[0]; conn.close()
        bot.reply_to(m, f"{LOGO}\n📊 אדמין | משתמשים: {count}" + SIGN)

@app.route("/")
def home(): return send_from_directory('web', 'index.html')

@app.route("/api/status")
def status():
    conn=sqlite3.connect(DB_NAME); count=conn.cursor().execute("SELECT COUNT(*) FROM wallets").fetchone()[0]; conn.close()
    return jsonify({"users": count, "status": "online"})

if __name__ == "__main__":
    if TOKEN:
        bot.polling(none_stop=True)
    else:
        app.run(host="0.0.0.0", port=8080)
