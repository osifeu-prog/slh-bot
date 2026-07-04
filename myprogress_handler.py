import json, os

def init(bot):
    @bot.message_handler(commands=['myprogress'])
    def my_progress(m):
        uid = str(m.chat.id)
        try:
            try:
            with open("state/db.json") as f:
                db = json.load(f)
        except Exception as e:
            bot.reply_to(m, f"❌ DB error: {e}")
            return
        except:
            bot.reply_to(m, "❌ DB error")
            return
        student = db.get("students", {}).get(uid)
        if not student:
            bot.reply_to(m, "❌ לא רשום. שלח /join")
            return
        name = student.get("name", "ללא שם")
        # קורס
        course = student.get("courses", {}).get("bitcoin_mastery", {})
        progress = course.get("progress", 0)
        stage = course.get("current_stage", 1)
        # פרויקטים
        active_proj = db.get("active_projects", {}).get(uid, "אין")
        # הפניות
        refs = student.get("referral_count", 0)
        # נקודות
        points = db.get("users", {}).get(uid, {}).get("points", 0)
        msg = f"👤 {name}\n"
        msg += f"📚 קורס: {progress}% (שלב {stage})\n"
        msg += f"📁 פרויקט פעיל: {active_proj}\n"
        msg += f"🔗 הפניות: {refs}\n"
        msg += f"⭐ נקודות: {points}"
        bot.reply_to(m, msg)
