import json
from core import profile_manager
from core.identity import OWNER_TELEGRAM_ID
from core.profile_manager import get_user
from core.invite_gate import can_start_onboarding

user_states = {}

def register(bot):

    @bot.message_handler(commands=['join'])
    def join_start(msg):
        uid = str(msg.from_user.id)

        if int(uid) == int(OWNER_TELEGRAM_ID):
            bot.reply_to(msg, "👑 OWNER — אינך צריך להירשם. שלח /start.")
            return

        existing_user = get_user(uid)

        if not can_start_onboarding(
            is_owner=False,
            is_existing_user=existing_user is not None,
        ):
            bot.reply_to(
                msg,
                "🚧 ההצטרפות לאלפא סגורה כרגע.\n"
                "נדרש Invite כדי להצטרף."
            )
            return

        user_states[uid] = {"step": "name"}
        bot.reply_to(msg, "👋 ברוך הבא! איך קוראים לך? (שם מלא)")

    @bot.message_handler(
        func=lambda m: str(m.from_user.id) in user_states
        and not str(m.text or "").startswith("/")
    )
    def join_steps(msg):
        uid = str(msg.from_user.id)

        if int(uid) == int(OWNER_TELEGRAM_ID):
            user_states.pop(uid, None)
            bot.reply_to(msg, "👑 OWNER — אין הרשמה פעילה.")
            return

        state = user_states[uid]
        step = state["step"]

        if step == "name":
            state["name"] = (msg.text or "").strip()
            state["step"] = "group"

            bot.reply_to(
                msg,
                f"נעים מאוד, {state['name']}!\n"
                "לאיזו קבוצה תרצה להצטרף?\n"
                "(לדוגמה: Bitcoin Masters, AI Builders)"
            )

        elif step == "group":
            group = (msg.text or "").strip()

            profile_manager.update_user(uid, {
                "name": state.get("name", ""),
                "group": group,
                "joined": True,
                "role": "student",
                "permissions": []
            })

            del user_states[uid]

            bot.reply_to(
                msg,
                f"✅ נרשמת בהצלחה, {state['name']}!\n"
                f"קבוצה: {group}\n\n"
                "מה תרצה לעשות עכשיו?\n"
                "📚 /courses\n"
                "💰 /wallet\n\n"
                "🔗 הצטרף לקבוצת העדכונים הרשמית:\n"
                "https://t.me/+9VUA_6jMyQcxMGVk"
                "🏆 /leaderboard"
            )

    @bot.message_handler(commands=['cancel_join'])
    def join_cancel(msg):
        uid = str(msg.from_user.id)

        if uid in user_states:
            del user_states[uid]
            bot.reply_to(msg, "❌ ההרשמה בוטלה.")
        else:
            bot.reply_to(msg, "אין הרשמה פעילה.")

print("join handler loaded")