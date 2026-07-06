import json, os

def init(bot):
    @bot.message_handler(commands=['myprogress'])
    def my_progress(m):
        uid = str(m.chat.id)
        try:
            with open("state/db.json") as f:
                db = json.load(f)
        except Exception as e:
            bot.reply_to(m, f"❌ DB error: {e}")
            return
        student = db.get("users", {}).get(uid)
        if not student:
            bot.reply_to(m, "❌ לא רשום. שלח /join")
            return
        name = student.get("name", "ללא שם")
        group = student.get("group", "")
        goal = student.get("goal", "")
        course = student.get("courses", {}).get("bitcoin_mastery", {})
        progress = course.get("progress", 0)
        stage = course.get("current_stage", 1)
        active_proj = db.get("active_projects", {}).get(uid, "אין")
        refs = student.get("referral_count", 0)
        points = db.get("users", {}).get(uid, {}).get("points", 0)
        msg = f"👤 {name}\n"
        if group:
            msg += f"🏫 קבוצה: {group}\n"
        if goal:
            msg += f"🎯 מטרה: {goal}\n"
        msg += f"📚 קורס: {progress}% (שלב {stage})\n"
        msg += f"📁 פרויקט פעיל: {active_proj}\n"
        msg += f"🔗 הפניות: {refs}\n"
        msg += f"⭐ נקודות: {points}"
        bot.reply_to(m, msg)
