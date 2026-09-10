from core import profile_manager
from core.identity import OWNER_TELEGRAM_ID
from core.profile_manager import user_exists
from core.invite_gate import can_start_onboarding
import state_manager

user_states = {}


def _consume_pending_referral(uid):
    uid = str(uid)

    def mutate(db):
        pending = db.setdefault("pending_referrals", {})
        return pending.pop(uid, None)

    return state_manager.atomic_update(mutate)


def register(bot):

    @bot.message_handler(commands=['join'])
    def join_start(msg):
        uid = str(msg.from_user.id)

        if int(uid) == int(OWNER_TELEGRAM_ID):
            bot.reply_to(msg, "👑 OWNER — אינך צריך להירשם. שלח /start.")
            return

        # Read-only existence check. get_user() creates missing users and must
        # never be used to decide whether a new user is already registered.
        existing_user = user_exists(uid)

        if not can_start_onboarding(
            is_owner=False,
            is_existing_user=existing_user,
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

            # The user is created only after the onboarding gate has already
            # passed. This prevents /start and /join from manufacturing an
            # "existing" user before registration is complete.
            profile_manager.update_user(uid, {
                "name": state.get("name", ""),
                "group": group,
                "joined": True,
                "role": "student",
                "permissions": []
            })

            try:
                from core.agent_registry import create_agent
                create_agent(f"user{uid}-Agent", owner_id=uid)
            except Exception as e:
                print("JOIN CREATE_AGENT FAILED:", e)
                bot.reply_to(
                    msg,
                    "⚠️ הפרופיל נשמר, אבל יצירת הסוכן האישי נכשלה.\n"
                    "ההרשמה לא תושלם עד לתיקון."
                )
                return

            try:
                from core.reward_engine import grant
                grant(
                    uid,
                    "welcome_bonus",
                    points=1000,
                    idempotency_key=f"welcome:{uid}"
                )
                print(f"WELCOME BONUS GRANTED: {uid}")
            except Exception as e:
                print("WELCOME BONUS FAILED:", e)

            try:
                from core.reward_engine import grant
                ref_uid = _consume_pending_referral(uid)
                if ref_uid and str(ref_uid) != uid:
                    grant(
                        str(ref_uid),
                        "referral",
                        points=10,
                        idempotency_key=f"ref:{uid}"
                    )
            except Exception as e:
                print("REFERRAL GRANT FAILED:", e)

            del user_states[uid]

            bot.reply_to(
                msg,
                f"✅ נרשמת בהצלחה, {state['name']}!\n"
                f"קבוצה: {group}\n\n"
                "הסוכן האישי שלך מוכן.\n\n"
                "מה תרצה לעשות עכשיו?\n"
                "🎯 שתף וצבור נקודות: /start\n"
                "💰 /wallet\n\n"
                "🔗 הצטרף לקבוצת העדכונים הרשמית:\n"
                "https://t.me/+9VUA_6jMyQcxMGVk\n"
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
