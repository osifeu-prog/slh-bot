from core.identity import OWNER_TELEGRAM_ID
from telebot import types
import state_manager

from core.message_utils import safe_clip
from core.profile_manager import user_exists, update_user
from core.agent_registry import create_agent
from core.identity_resolver import get_display_name
from core.invite_gate import can_start_onboarding


def _set_pending_referral(uid, ref_uid):
    uid = str(uid)
    ref_uid = str(ref_uid)

    def mutate(db):
        pending = db.setdefault("pending_referrals", {})
        if uid not in pending:
            pending[uid] = ref_uid
        return pending[uid]

    return state_manager.atomic_update(mutate)


def _get_pending_referral(uid):
    db = state_manager.load_db()
    return (db.get("pending_referrals") or {}).get(str(uid))


def _has_valid_invite(uid):
    ref_uid = _get_pending_referral(uid)
    return bool(
        ref_uid
        and str(ref_uid) != str(uid)
        and user_exists(str(ref_uid))
    )


def load_branding():
    try:
        from datetime import datetime
        date_greg = datetime.now().strftime("%Y-%m-%d")
        logo_lines = [
            'בס"ד',
            "███████╗██╗     ██╗  ██╗",
            "██╔════╝██║     ██║  ██║",
            "███████╗██║     ███████║",
            "╚════██║██║     ██║  ██║",
            "███████║███████╗██║  ██║",
            "╚══════╝╚══════╝╚═╝  ╚═╝",
            "",
            "SLH SYSTEM",
            "Smart Layer Hub",
            "🌟 רובוטוש",
            "🆔 972500000001",
            "🔗 BRIDGE: PC_Osif2 (online)",
            f"Updated: {date_greg}",
        ]
        return "\n".join(logo_lines)
    except Exception:
        return ""


def register(bot, context=None):
    context = context or {}

    def runtime_bot_username():
        username = context.get("telegram_bot_username") or context.get("bot_username")
        if username:
            return str(username).lstrip("@").strip()
        try:
            me = bot.get_me()
            return getattr(me, "username", None)
        except Exception:
            return None

    def referral_link(user_id):
        username = runtime_bot_username()
        if not username:
            return None
        return f"https://t.me/{username}?start=ref_{user_id}"

    def send_dashboard(chat_id, user_id):
        db = state_manager.load_db()
        user = db.get("users", {}).get(str(user_id), {})
        wallet = user.get("wallet", {})
        credits = wallet.get("credits", 0)
        course = user.get("active_course", "אין")
        owned_agents = [
            agent for agent in db.get("agents", {}).values()
            if isinstance(agent, dict) and str(agent.get("owner_id", "")) == str(user_id)
        ]
        text = (
            "🌟 ה-Dashboard שלך\n\n"
            f"💰 Credits: {credits}\n"
            f"📚 קורס פעיל: {course}\n"
            f"🤖 הסוכנים שלך: {len(owned_agents)}\n\n"
            "מה תרצה לעשות?"
        )
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("📚 המשך לקורס", callback_data="continue_course"))
        markup.add(types.InlineKeyboardButton("🤖 צור סוכן חדש", callback_data="create_agent"))
        markup.add(types.InlineKeyboardButton("📊 סטטוס מערכת", callback_data="system_status"))
        bot.send_message(chat_id, safe_clip(text), reply_markup=markup)

    @bot.message_handler(commands=["start"])
    def start(m):
        user_id = str(m.from_user.id)
        user_name = get_display_name(user_id, m.from_user) or "חבר"
        is_owner = int(user_id) == int(OWNER_TELEGRAM_ID)
        is_new = not user_exists(user_id)

        try:
            from core.holiday_campaign import record_entry
            record_entry(user_id)
        except Exception as e:
            print("HOLIDAY CAMPAIGN ENTRY FAILED:", e)

        parts = (m.text or "").split(maxsplit=1)
        if is_new and len(parts) > 1 and parts[1].startswith("ref_"):
            ref_uid = parts[1][4:].strip()
            if ref_uid and ref_uid != user_id and user_exists(ref_uid):
                _set_pending_referral(user_id, ref_uid)

        # Existing accounts should resume their personal system directly.
        # Do this before the new-user Alpha onboarding card is rendered.
        if not is_new and not is_owner:
            send_dashboard(m.chat.id, user_id)
            return

        has_valid_invite = _has_valid_invite(user_id)
        if not can_start_onboarding(
            is_owner=is_owner,
            is_existing_user=not is_new,
            has_invite=has_valid_invite,
        ):
            bot.send_message(
                m.chat.id,
                "🚧 ההצטרפות לאלפא סגורה כרגע.\n"
                "נדרש Invite כדי להצטרף.\n\n"
                "אם יש לך Invite, פתח את הקישור שקיבלת ואז שלח /join."
            )
            return

        from datetime import datetime
        now = datetime.now().strftime("%Y-%m-%d")
        db = state_manager.load_db()
        user_wallet = db.get("users", {}).get(user_id, {}).get("wallet", {})
        credits = user_wallet.get("credits", 0)
        staked = user_wallet.get("staked", 0)
        invite_link = referral_link(user_id)
        invite_line = (
            f"📎 קישור ההזמנה האישי שלך:\n{invite_link}"
            if invite_link else
            "📎 קישור ההזמנה האישי שלך: יופיע לאחר זיהוי הבוט"
        )

        if is_owner:
            branding = load_branding()
            if branding:
                try:
                    bot.send_message(m.chat.id, f"<pre>{branding}</pre>", parse_mode="HTML")
                except Exception:
                    pass
            text = (
                f"ברוך שובך, {user_name}!\n\n"
                f"📅 {now}\n"
                f"👤 משתמש: {user_name}\n"
                f"💰 יתרה: {credits}\n"
                f"🔒 סטייקינג: {staked}\n\n"
                "אני רובוטוש, העוזר האישי שלך.\n"
                "👑 המערכת מזהה אותך כבעלים של SLH OS.\n"
                "🚀 ה-Dashboard והמערכת האישית שלך מוכנים.\n\n"
                "🔗 הצטרף לקבוצת העדכונים הרשמית:\n"
                "https://t.me/+9VUA_6jMyQcxMGVk\n\n"
                f"{invite_line}"
            )
            bot.send_message(m.chat.id, text)
            return

        text = (
            f"ברוך הבא, {user_name}!\n\n"
            "ברוך הבא ל-SLH OS.\n"
            "כדי להתחיל, הצטרף למסלול ה-Alpha:\n"
            "1️⃣ הרשמה\n"
            "2️⃣ פרופיל + Personal Agent\n"
            "3️⃣ Academy + שיעור ראשון\n"
            "4️⃣ נקודות + Referral\n"
            "5️⃣ Credits דרך Telegram Stars\n\n"
            "הצטרפות אינה מפעילה חשבון לפני השלמת /join."
        )
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("🚀 הצטרף ל-SLH", callback_data="start_join"))
        markup.add(types.InlineKeyboardButton("📖 עזרה", callback_data="show_help"))
        bot.send_message(m.chat.id, text, reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: call.data == "start_join")
    def start_join(call):
        user_id = str(call.from_user.id)
        is_owner = int(user_id) == int(OWNER_TELEGRAM_ID)
        existing_user = user_exists(user_id)
        has_valid_invite = _has_valid_invite(user_id)
        if not can_start_onboarding(
            is_owner=is_owner,
            is_existing_user=existing_user,
            has_invite=has_valid_invite,
        ):
            bot.answer_callback_query(call.id, "🚧 ההצטרפות לאלפא סגורה כרגע.")
            return
        if is_owner or existing_user:
            bot.answer_callback_query(call.id, "החשבון כבר קיים")
            bot.send_message(call.message.chat.id, "החשבון כבר קיים. פתח /dashboard")
            return
        from handlers.join_handler import user_states
        user_states[user_id] = {"step": "name"}
        bot.answer_callback_query(call.id, "🚀 מתחילים")
        bot.send_message(call.message.chat.id, "👋 ברוך הבא! איך קוראים לך? (שם מלא)")

    @bot.callback_query_handler(func=lambda call: call.data == "show_help")
    def show_help(call):
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id,
            "SLH Alpha\n\n"
            "/join — הרשמה\n"
            "/academy — Academy\n"
            "/pay — Credits דרך Telegram Stars\n"
            "/wallet — ארנק Credits\n"
            "/stake <amount> — Staking פנימי\n"
            "/dashboard — לוח אישי"
        )

    # Backward-compatible callback retained for existing keyboards/messages.
    @bot.callback_query_handler(func=lambda call: call.data == "onboard_start")
    def onboard_start(call):
        user_id = str(call.from_user.id)
        try:
            is_owner = int(user_id) == int(OWNER_TELEGRAM_ID)
            is_existing = user_exists(user_id)
            has_valid_invite = _has_valid_invite(user_id)
            if not can_start_onboarding(
                is_owner=is_owner,
                is_existing_user=is_existing,
                has_invite=has_valid_invite,
            ):
                bot.answer_callback_query(call.id, "🚧 ההצטרפות לאלפא סגורה כרגע.")
                return
            if is_existing or is_owner:
                bot.answer_callback_query(call.id, "החשבון כבר קיים")
                send_dashboard(call.message.chat.id, user_id)
                return
            from handlers.join_handler import user_states
            user_states[user_id] = {"step": "name"}
            bot.answer_callback_query(call.id, "🚀 מתחילים")
            bot.send_message(call.message.chat.id, "👋 ברוך הבא! איך קוראים לך? (שם מלא)")
        except Exception as e:
            bot.answer_callback_query(call.id, "❌ שגיאה")
            bot.send_message(call.message.chat.id, f"❌ Onboarding start failed: {type(e).__name__}")

    @bot.callback_query_handler(func=lambda call: call.data == "continue_course")
    def continue_course(call):
        bot.answer_callback_query(call.id, "📚 המשך לקורס")
        bot.send_message(
            call.message.chat.id,
            "📚 הקורס הפעיל שלך: bitcoin_mastery\n"
            "שלח /lesson bitcoin_mastery 1 כדי להתחיל."
        )

    @bot.callback_query_handler(func=lambda call: call.data == "system_status")
    def system_status(call):
        bot.answer_callback_query(call.id, "📊 סטטוס מערכת")
        bot.send_message(
            call.message.chat.id,
            "🖥 SLH OS\n"
            "שירות פעיל, DB פעיל, LLM תקין.\n"
            "שלח /doctor לדוח מלא."
        )

    @bot.callback_query_handler(func=lambda call: call.data == "goto_dashboard")
    def goto_dashboard(call):
        bot.answer_callback_query(call.id)
        send_dashboard(call.message.chat.id, str(call.from_user.id))

    @bot.callback_query_handler(func=lambda call: call.data == "create_agent")
    def create_agent_callback(call):
        user_id = str(call.from_user.id)
        try:
            agent_id, agent = create_agent(f"user{user_id}-Agent", owner_id=user_id)
            bot.answer_callback_query(call.id, "🤖 הסוכן נוצר")
            bot.send_message(call.message.chat.id, "✅ הסוכן נוצר בהצלחה\n" f"🆔 ID: {agent_id}")
        except ValueError as e:
            bot.answer_callback_query(call.id, "⚠️ הסוכן כבר קיים")
            bot.send_message(call.message.chat.id, f"⚠️ {e}")
        except Exception as e:
            bot.answer_callback_query(call.id, "❌ שגיאה")
            bot.send_message(call.message.chat.id, f"❌ Agent creation failed: {type(e).__name__}")
