from core import profile_manager
from core.identity import OWNER_TELEGRAM_ID
from core.profile_manager import user_exists
from core.invite_gate import can_start_onboarding
import state_manager

user_states = {}


def _get_pending_referral(uid):
    db = state_manager.load_db()
    return (db.get("pending_referrals") or {}).get(str(uid))


def _clear_pending_referral(uid):
    uid = str(uid)

    def mutate(db):
        pending = db.setdefault("pending_referrals", {})
        return pending.pop(uid, None)

    return state_manager.atomic_update(mutate)


def _persist_referral(uid, ref_uid):
    """Persist the successful referral relationship exactly once."""
    uid = str(uid)
    ref_uid = str(ref_uid)

    if not ref_uid or ref_uid == uid:
        return False

    def mutate(db):
        users = db.setdefault("users", {})
        user = users.get(uid)
        referrer = users.get(ref_uid)
        if not user or not referrer:
            return False

        referral = user.setdefault("referral", {})
        existing = referral.get("referred_by")
        if existing:
            return str(existing) == ref_uid

        referral["referred_by"] = ref_uid
        referral["referred_at"] = __import__("datetime").datetime.utcnow().isoformat()

        ref_profile = referrer.setdefault("referral", {})
        ref_profile["count"] = int(ref_profile.get("count", 0) or 0) + 1
        return True

    return state_manager.atomic_update(mutate)


def register(bot):

    @bot.message_handler(commands=['join'])
    def join_start(msg):
        uid = str(msg.from_user.id)

        # Capture campaign-day entry on the actual /join path as well as /start.
        # This is attribution bookkeeping only and never changes SLH balances.
        try:
            from core.holiday_campaign import record_entry
            record_entry(uid, source="join_command")
        except Exception as e:
            print("HOLIDAY CAMPAIGN JOIN ENTRY FAILED:", e)

        if int(uid) == int(OWNER_TELEGRAM_ID):
            bot.reply_to(msg, "👑 OWNER — אינך צריך להירשם. שלח /start.")
            return

        existing_user = user_exists(uid)
        pending_referral = _get_pending_referral(uid)
        has_valid_invite = bool(
            pending_referral
            and str(pending_referral) != uid
            and user_exists(str(pending_referral))
        )

        if not can_start_onboarding(
            is_owner=False,
            is_existing_user=existing_user,
            has_invite=has_valid_invite,
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

            try:
                from core.agent_registry import create_agent
                create_agent(f"user{uid}-Agent", owner_id=uid)
            except Exception as e:
                print("JOIN CREATE_AGENT FAILED:", e)
                bot.reply_to(
                    msg,
                    "⚠️ יצירת הסוכן האישי נכשלה.\n"
                    "ההרשמה לא הושלמה. נסה שוב מאוחר יותר."
                )
                return

            try:
                profile_manager.update_user(uid, {
                    "name": state.get("name", ""),
                    "group": group,
                    "joined": True,
                    "role": "student",
                    "permissions": []
                })
            except Exception as e:
                print("JOIN PROFILE UPDATE FAILED:", e)
                bot.reply_to(
                    msg,
                    "⚠️ שמירת הפרופיל נכשלה.\n"
                    "ההרשמה לא הושלמה. נסה שוב מאוחר יותר."
                )
                return

            # Finalize the holiday campaign entry only after onboarding
            # has successfully persisted joined=True.
            try:
                from core.holiday_campaign import finalize_entry
                finalized = finalize_entry(uid)
                print(f"HOLIDAY CAMPAIGN FINALIZE: {uid} -> {finalized}")
            except Exception as e:
                print("HOLIDAY CAMPAIGN FINALIZE FAILED:", e)

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
                ref_uid = _get_pending_referral(uid)
                if ref_uid and str(ref_uid) != uid and user_exists(str(ref_uid)):
                    persisted = _persist_referral(uid, ref_uid)
                    if persisted:
                        grant(
                            str(ref_uid),
                            "referral",
                            points=10,
                            idempotency_key=f"ref:{uid}"
                        )
                        try:
                            from core.holiday_campaign import settle
                            settlement = settle(str(ref_uid))
                            print(
                                f"HOLIDAY CAMPAIGN SETTLEMENT: "
                                f"{ref_uid} -> {settlement}"
                            )
                        except Exception as e:
                            print("HOLIDAY CAMPAIGN SETTLEMENT FAILED:", e)
                    _clear_pending_referral(uid)
            except Exception as e:
                print("REFERRAL GRANT FAILED:", e)

            user_states.pop(uid, None)

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
