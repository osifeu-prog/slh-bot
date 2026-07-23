from telebot import types
import json

def register(bot):
    @bot.message_handler(commands=['start'])
    def start(m):
        user_id = str(m.from_user.id)
        user_name = m.from_user.first_name
        try:
            with open('state/db.json', 'r') as f:
                db = json.load(f)
        except:
            db = {"users": {}}
        is_new = user_id not in db.get("users", {})
        if is_new:
            text = f"""ברוך הבא, {user_name}!
אני *רובוטוש*, העוזר האישי שלך.
תוך 2 דקות תקבל:
✅ קורס השקעות ראשון
🤖 סוכן AI אישי
🎁 100 SLH במתנה
מוכן להתחיל?"""
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🚀 כן, תתחיל אותי!", callback_data="onboard_start"))
        else:
            text = f"""ברוך שובך, {user_name}!
ה-Dashboard שלך מחכה לך עם כל העדכונים.
מה תרצה לעשות?"""
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("📊 לך ל-Dashboard", callback_data="goto_dashboard"))
            markup.add(types.InlineKeyboardButton("🤖 צור סוכן חדש", callback_data="create_agent"))
        bot.send_message(m.chat.id, text, reply_markup=markup, parse_mode="Markdown")
