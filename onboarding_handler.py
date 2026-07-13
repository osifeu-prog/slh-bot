import json
from datetime import datetime
from telebot import types

DB_PATH = "state/db.json"


def load_db():
    with open(DB_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_db(db):
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)


def update_onboarding(uid, data):
    db = load_db()
    uid = str(uid)

    if uid not in db.get("users", {}):
        return

    user = db["users"][uid]

    user.setdefault("onboarding", {})
    user["onboarding"].update(data)

    if data.get("completed"):
        user.setdefault("ai", {})
        user["ai"]["initialized"] = True

    save_db(db)


def init(bot):

    @bot.callback_query_handler(func=lambda c: c.data == "onboarding_start")
    def start_onboarding(call):
        print("🔥 ONBOARDING START CALLBACK:", call.from_user.id, call.data)

        update_onboarding(
            call.from_user.id,
            {"stage": "questions"}
        )

        bot.answer_callback_query(call.id)

        kb = types.InlineKeyboardMarkup()
        kb.add(
            types.InlineKeyboardButton(
                "🚀 הפעל SLH AI",
                callback_data="onboarding_ai"
            )
        )

        bot.send_message(
            call.message.chat.id,
            """
🚀 ברוכים הבאים ל־SLH onboarding

אני מכין לך סביבת עבודה אישית:

✅ ארנק
✅ אקדמיה
✅ סוכן AI אישי
✅ מערכת משימות

לחץ להתחלה:
""",
            reply_markup=kb
        )


    @bot.callback_query_handler(func=lambda c: c.data == "onboarding_ai")
    def activate_ai(call):
        print("🔥 ONBOARDING AI CALLBACK:", call.from_user.id, call.data)

        update_onboarding(
            call.from_user.id,
            {
                "completed": True,
                "stage": "completed",
                "completed_at": datetime.now().isoformat()
            }
        )

        bot.answer_callback_query(call.id)

        bot.send_message(
            call.message.chat.id,
            """
🎉 SLH OS מוכן!

AI אישי הופעל ✅

המערכת שלך פעילה:
🤖 AI
📚 Academy
💰 Wallet
🧠 Memory
"""
        )
