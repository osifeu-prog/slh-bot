import json

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
        msg = "🌟 **ברוכים הבאים ל-SLH Learning!** 🌟\n\n"
        if name:
            msg = f"נעים לראותך שוב, {name}!\n\n" + msg
        msg += "🎯 **הצעדים הראשונים:**\n"
        msg += "1️⃣ /join – הרשמה\n"
        msg += "2️⃣ /courses – צפייה בקורס\n"
        msg += "3️⃣ /project create – פרויקט אישי\n"
        msg += "4️⃣ /project task add – הוספת משימות\n"
        msg += "5️⃣ /myprogress – מעקב התקדמות\n"
        msg += "6️⃣ /referral – הזמנת חברים\n\n"
        msg += "👥 **בואו נבנה יחד!**"
        bot.reply_to(message, msg, parse_mode="Markdown")
