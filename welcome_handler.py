import telebot
from telebot import types
import json
from datetime import datetime

DB_PATH="state/db.json"

def ensure_onboarding_user(uid):
    uid=str(uid)
    try:
        with open(DB_PATH, encoding="utf-8") as f:
            db = json.load(f)
    except:
        return
    if uid not in db.get("users", {}):
        return
    user = db["users"][uid]
    user.setdefault("onboarding", {})
    user["onboarding"]["completed"] = True
    user.setdefault("ai", {})
    user["ai"]["initialized"] = True
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)

def init(bot):
    @bot.message_handler(commands=['start'])
    def send_welcome(message):
        uid = str(message.chat.id)
        name = ""
        try:
            with open("db.json") as f:
                db = json.load(f)
                if uid in db.get("students", {}):
                    name = db["students"][uid].get("name", "")
        except:
            pass
        

        # טעינת הלוגו
        import os
        logo_path = os.path.join(os.path.dirname(__file__), "logo.txt")
        try:
            with open(logo_path, "r", encoding="utf-8") as f:
                logo = f.read().strip()
        except:
            logo = "🌟 SLH OS"

        msg = f"{logo}\n\n🌟 **ברוכים הבאים ל-SLH OS!** 🚀\n\n"
        if name:
            msg = f"נעים לראותך שוב, {name}!\n\n" + msg
        
        msg += "🟢 **מצב מערכת**\n"
        msg += "• סטטוס מערכת — /status\n"
        msg += "• בריאות מערכת — /health\n"
        msg += "• אבחון מלא — /test\n"
        msg += "• אבחון סוכנים — /test_agents\n\n"
        
        msg += "🤖 **סוכנים**\n"
        msg += "• רשימת סוכנים — /agents\n"
        msg += "• צור סוכן — /agent_create\n"
        msg += "• שלח הודעה — /sendagent\n"
        msg += "• תיבת סוכן — /inbox\n\n"
        
        msg += "🧠 **AI & מודולים**\n"
        msg += "• רישום AI — /register_ai\n"
        msg += "• שאל AI — /ask\n"
        msg += "• יומן חכם — /journal_ask\n"
        msg += "• מודולים — /plugin list\n\n"
        
        msg += "💰 **כלכלה**\n"
        msg += "• יתרה — /balance\n"
        msg += "• קנייה — /buy\n"
        msg += "• תשלום — /pay\n"
        msg += "• טוקן — /token balance\n\n"
        
        msg += "📚 **למידה**\n"
        msg += "• קורסים — /courses\n"
        msg += "• התקדמות — /myprogress\n"
        msg += "• הפניות — /referral\n\n"
        
        msg += "🔧 **אדמין**\n"
        msg += "• פאנל אדמין — /admin\n"
        msg += "• גיבוי — /backup\n"
        msg += "• ריסטארט — /restart\n"
        msg += "• לוגים — /logs 20\n\n"
        
        msg += "👥 **בואו נבנה יחד!**"
        
        bot.reply_to(message, msg, parse_mode="Markdown")

    @bot.message_handler(commands=['join'])
    def join(m):
        uid = str(m.from_user.id)
        name = m.from_user.first_name or "ללא שם"
        db = json.load(open("db.json"))
        if "students" not in db:
            db["students"] = {}
        if uid in db["students"]:
            bot.reply_to(m, "אתה כבר רשום!")
            return
        db["students"][uid] = {
            "name": name,
            "referral_count": 0,
            "courses": {}
        }
        json.dump(db, open("db.json","w"), indent=2, ensure_ascii=False)
        bot.reply_to(m, f"ברוך הבא, {name}! נרשמת בהצלחה.\nשלח /start_course להתחיל.")
