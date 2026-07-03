import json

def init(bot):
    @bot.message_handler(commands=['start'])
    def send_welcome(message):
        uid = str(message.chat.id)
        name = ""
        try:
            with open("state/db.json") as f:
                db = json.load(f)
                if uid in db.get("students", {}):
                    name = db["students"][uid].get("name", "")
        except:
            pass
        msg = "🌟 **ברוכים הבאים ל-SLH Learning!** 🌟\n\n"
        if name:
            msg = f"נעים לראותך שוב, {name}!\n\n" + msg
        msg += "🎯 **פקודות עיקריות:**\n"
        msg += "1️⃣ /join – הרשמה\n"
        msg += "2️⃣ /courses – צפייה בקורסים\n"
        msg += "3️⃣ /project create – פרויקט אישי\n"
        msg += "4️⃣ /project task add – הוספת משימות\n"
        msg += "5️⃣ /myprogress – מעקב התקדמות\n"
        msg += "6️⃣ /referral – הזמנת חברים\n\n"
        msg += "🤖 **סוכנים חכמים:**\n"
        msg += "/agent\_create \<name\> – צור סוכן\n"
        msg += "/agents – רשימת סוכנים\n"
        msg += "/sendagent \<prefix\> \<msg\> – שלח הודעה\n"
        msg += "/inbox \<prefix\> – תיבת הודעות\n"
        msg += "/agentstate \<prefix\> \<state\> – שנה מצב\n\n"
        msg += "📋 **התנסות מהירה:**\n"
        msg += "/demo – תפריט דמו\n"
        msg += "/demo agents – צור סוכני דמו\n"
        msg += "/demo tasks – משימות לדוגמה\n"
        msg += "/demo guide – מדריך מהיר\n\n"
        msg += "👥 **בואו נבנה יחד!**"
        bot.reply_to(message, msg, parse_mode="Markdown")
    @bot.message_handler(commands=['join'])
    def join(m):
        uid = str(m.from_user.id)
        name = m.from_user.first_name or "ללא שם"
        db = json.load(open("state/db.json"))
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
        json.dump(db, open("state/db.json","w"), indent=2, ensure_ascii=False)
        bot.reply_to(m, f"ברוך הבא, {name}! נרשמת בהצלחה.\nשלח /start_course להתחיל.")
