from core.identity import OWNER_TELEGRAM_ID
from telebot import types
import state_manager

from core.message_utils import safe_clip
from core.profile_manager import user_exists, update_user
from core.agent_registry import create_agent
from core.identity_resolver import get_display_name
from core.invite_gate import can_start_onboarding
from core.investor_read_model import get_investor_snapshot


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


def _bridge_status_display():
    try:
        from core.device_read_model import get_device_status
        info = get_device_status("PC_Osif2", ttl_seconds=120)
        return f"{info.get('status_icon', '⚪️')} {info.get('status', 'unknown')}"
    except Exception:
        return "⚪️ unknown"


def _hebrew_date_display(gregorian_date):
    try:
        import hdate
        from hdate.gematria import hebrew_number
        from hdate.translator import set_language

        set_language("he")
        hd = hdate.HDateInfo(gregorian_date).hdate
        return f"{hebrew_number(hd.day)} ב{hd.month} {hebrew_number(hd.year)}"
    except Exception:
        return ""


def load_branding(bot=None):
    try:
        from datetime import datetime
        from zoneinfo import ZoneInfo

        now = datetime.now(ZoneInfo("Asia/Jerusalem"))
        date_greg = now.strftime("%Y-%m-%d")
        date_hebrew = _hebrew_date_display(now.date())

        bot_id = "unknown"
        if bot is not None:
            try:
                bot_id = str(bot.get_me().id)
            except Exception:
                pass

        logo_lines = [
            'בס"ד',
            f"📅 {date_hebrew}" if date_hebrew else f"📅 {date_greg}",
            "SLH SYSTEM — Smart Layer Hub",
            "🌟 רובוטוש",
            f"🆔 {bot_id}",
            f"🔗 BRIDGE: PC_Osif2 ({_bridge_status_display()})",
            f"Updated: {date_greg}",
            "",
            "███████╗██╗     ██╗  ██╗",
            "██╔════╝██║     ██║  ██╗",
            "███████╗██║     ███████║",
            "╚════██║██║     ██║  ██╗",
            "███████║███████╗██║  ██╗",
            "╚══════╝╚══════╝╚═╝  ╚═╝",
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

    def _ton_label(uid, wallet):
        """Display the verified TON binding first, with legacy fallback."""
        try:
            from core.ton_wallet_binding import get_ton_binding
            binding = get_ton_binding(str(uid))
        except Exception:
            binding = None
        address = (binding or {}).get("address") or (wallet or {}).get("ton_wallet")
        if not address:
            return "לא מקושר"
        address = str(address)
        short = address if len(address) <= 14 else f"{address[:6]}…{address[-4:]}"
        return f"✅ {short}" if binding else short

    def _personal_dashboard_text(user_id):
        snapshot = get_investor_snapshot(str(user_id))
        identity = snapshot.get("identity", {})
        wallet = snapshot.get("wallet", {})
        academy = snapshot.get("academy", {})
        tasks = snapshot.get("tasks", {})
        db = state_manager.load_db()
        owned_agents = [
            agent for agent in db.get("agents", {}).values()
            if isinstance(agent, dict) and str(agent.get("owner_id", "")) == str(user_id)
        ]
        display_name = identity.get("display_name") or get_display_name(str(user_id)) or "חבר"
        enrolled = academy.get("enrolled", [])
        course_line = (
            f"📚 קורסים: {len(enrolled)}"
            if isinstance(enrolled, list)
            else "📚 קורסים: 0"
        )
        internal_token = wallet.get("live_token_balance")
        if internal_token in (None, ""):
            internal_token = wallet.get("token_balance", 0)

        return (
            f"🌟 {display_name} — ה-Dashboard שלך\n\n"
            f"🧾 כל היתרות:\n"
            f"💰 Credits: {wallet.get('credits', 0)}\n"
            f"🔒 Staked: {wallet.get('staked', 0)}\n"
            f"🪙 Internal SLH: {internal_token}\n"
            f"💎 TON Wallet: {_ton_label(user_id, wallet)}\n\n"
            f"{course_line}\n"
            f"🤖 הסוכנים שלך: {len(owned_agents)}\n"
            f"🎯 משימות פתוחות: {tasks.get('open', 0)}\n\n"
            "מה תרצה לעשות?"
        )

    def _trade_button_label(user_id):
        labels = {
            "he": "🚀 Trade Terminal",
            "en": "🚀 Trade Terminal",
            "ar": "🚀 منصة تداول SLH",
            "es": "🚀 Terminal de Trading SLH",
            "ru": "🚀 SLH Trade Terminal",
            "pt": "🚀 Terminal de Trading SLH",
        }
        try:
            from language_handler import get_lang
            return labels.get(get_lang(user_id), labels["he"])
        except Exception:
            return labels["he"]

    def _dashboard_markup(user_id):
        markup = types.InlineKeyboardMarkup(row_width=3)
        markup.add(
            types.InlineKeyboardButton("👛 ארנק", callback_data="menu_wallet"),
            types.InlineKeyboardButton("📚 Academy", callback_data="continue_course"),
            types.InlineKeyboardButton("🎯 משימות", callback_data="menu_missions"),
        )
        markup.add(
            types.InlineKeyboardButton("🤖 סוכנים", callback_data="menu_agents"),
            types.InlineKeyboardButton("🧠 AI", callback_data="menu_ai"),
            types.InlineKeyboardButton("🎁 Rewards", callback_data="gifts:home"),
        )
        markup.add(
            types.InlineKeyboardButton("👥 הזמנה", callback_data="menu_share"),
            types.InlineKeyboardButton("📊 מערכת", callback_data="system_status"),
            types.InlineKeyboardButton("🔄 רענון", callback_data="refresh_dashboard"),
        )
        markup.add(
            types.InlineKeyboardButton(_trade_button_label(user_id), callback_data="trade:home"),
        )
        markup.add(
            types.InlineKeyboardButton(
                "🚀 Mini App",
                web_app=types.WebAppInfo(
                    url="https://slh-cloud-bot-production.up.railway.app/mini-app-v4?v=20260925-dashboard"
                ),
            )
        )
        return markup

    def send_dashboard(chat_id, user_id):
        text = _personal_dashboard_text(user_id)
        bot.send_message(
            chat_id,
            safe_clip(text),
            reply_markup=_dashboard_markup(user_id),
        )

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
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo("Asia/Jerusalem")).strftime("%Y-%m-%d")
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
            # Owner /start is the canonical personal control surface.
            # Keep branding, balances and dashboard actions together in one message.
            branding = load_branding(bot)
            dashboard_text = _personal_dashboard_text(user_id)
            owner_text = (
                f"ברוך שובך, {user_name}!\n\n"
                "אני רובוטוש, העוזר האישי שלך.\n"
                "👑 המערכת מזהה אותך כבעלים של SLH OS.\n"
                "🚀 המערכת האישית שלך מוכנה.\n\n"
                "🔗 הצטרף לקבוצת העדכונים הרשמית:\n"
                "https://t.me/+9VUA_6jMyQcxMGVk\n\n"
                f"{invite_line}"
            )
            combined_text = "\n\n".join(
                part
                for part in (
                    f"<pre>{branding}</pre>" if branding else "",
                    owner_text,
                    dashboard_text,
                )
                if part
            )
            markup = _dashboard_markup(user_id)
            bot.send_message(
                m.chat.id,
                safe_clip(combined_text),
                parse_mode="HTML" if branding else None,
                reply_markup=markup,
            )
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
        markup.add(types.InlineKeyboardButton("🎁 מתנות ו-Airdrop", callback_data="gifts:home"))
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
            "/gifts — מתנות, Rewards ו-Airdrop\n"
            "/gift <uid> <amount> — שליחת מתנת Credits\n"
            "/stake <amount> — Staking פנימי\n"
            "/dashboard — לוח אישי\n"
            "/trade — SLH Trade Terminal"
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
        bot.answer_callback_query(call.id, "📚 פותח את ה-Academy")
        from handlers.academy_menu_handler import _send_academy
        _send_academy(bot, call.message.chat.id, str(call.from_user.id))

    @bot.callback_query_handler(func=lambda call: call.data == "menu_wallet")
    def menu_wallet(call):
        bot.answer_callback_query(call.id)
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(types.InlineKeyboardButton("💰 יתרה", callback_data="wallet_balance"), types.InlineKeyboardButton("↔️ העברה", callback_data="wallet_transfer"))
        markup.add(types.InlineKeyboardButton("📈 Staking", callback_data="wallet_staking"), types.InlineKeyboardButton("🧾 היסטוריה", callback_data="wallet_history"))
        markup.add(types.InlineKeyboardButton("⬅️ חזרה", callback_data="goto_dashboard"))
        bot.send_message(call.message.chat.id, "👛 הארנק שלך\nבחר פעולה:", reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: call.data == "menu_agents")
    def menu_agents(call):
        bot.answer_callback_query(call.id)
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("🤖 הסוכנים שלי", callback_data="agents_list"))
        markup.add(types.InlineKeyboardButton("➕ צור סוכן", callback_data="create_agent"))
        markup.add(types.InlineKeyboardButton("⬅️ חזרה", callback_data="goto_dashboard"))
        bot.send_message(call.message.chat.id, "🤖 Agents\nנהל את הסוכנים שלך:", reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: call.data == "menu_ai")
    def menu_ai(call):
        bot.answer_callback_query(call.id)
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("🧠 שאל את SLH AI", callback_data="ai_prompt"))
        markup.add(types.InlineKeyboardButton("⬅️ חזרה", callback_data="goto_dashboard"))
        bot.send_message(call.message.chat.id, "🧠 SLH AI\nהעוזר שלך מחובר למערכת.", reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: call.data == "menu_missions")
    def menu_missions(call):
        bot.answer_callback_query(call.id)
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("🎯 המשימות שלי", callback_data="missions_list"))
        markup.add(types.InlineKeyboardButton("🏆 התקדמות", callback_data="progress_view"))
        markup.add(types.InlineKeyboardButton("⬅️ חזרה", callback_data="goto_dashboard"))
        bot.send_message(call.message.chat.id, "🎯 Missions\nהמשך מהנקודה האחרונה שלך:", reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: call.data == "menu_share")
    def menu_share(call):
        bot.answer_callback_query(call.id)
        link = referral_link(str(call.from_user.id))
        text = "👥 הזמנה ל-SLH\n\n" + (f"שתף את הקישור שלך:\n{link}" if link else "קישור ההזמנה יופיע לאחר זיהוי הבוט.")
        bot.send_message(call.message.chat.id, text)

    @bot.callback_query_handler(func=lambda call: call.data == "wallet_balance")
    def wallet_balance(call):
        bot.answer_callback_query(call.id)
        uid = str(call.from_user.id)
        wallet = state_manager.load_db().get("users", {}).get(uid, {}).get("wallet", {})
        bot.send_message(call.message.chat.id, f"💰 Credits: {wallet.get('credits', 0)}\n🔒 Staked: {wallet.get('staked', 0)}")

    @bot.callback_query_handler(func=lambda call: call.data == "wallet_transfer")
    def wallet_transfer(call):
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "↔️ העברה: /transfer USER_ID AMOUNT")

    @bot.callback_query_handler(func=lambda call: call.data == "wallet_staking")
    def wallet_staking(call):
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "📈 Staking: /stake AMOUNT\nאו /stake_lock AMOUNT DAYS")

    @bot.callback_query_handler(func=lambda call: call.data == "wallet_history")
    def wallet_history(call):
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "🧾 היסטוריה: /history")

    @bot.callback_query_handler(func=lambda call: call.data == "agents_list")
    def agents_list(call):
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "🤖 הסוכנים שלך: /agents")

    @bot.callback_query_handler(func=lambda call: call.data == "ai_prompt")
    def ai_prompt(call):
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "🧠 שאל אותי כאן: /ask מה תרצה לדעת?")

    @bot.callback_query_handler(func=lambda call: call.data == "missions_list")
    def missions_list(call):
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "🎯 המשימות שלך: /mission")

    @bot.callback_query_handler(func=lambda call: call.data == "progress_view")
    def progress_view(call):
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "🏆 ההתקדמות שלך: /progress")

    @bot.callback_query_handler(func=lambda call: call.data == "system_status")
    def system_status(call):
        bot.answer_callback_query(call.id, "📊 סטטוס מערכת")
        bot.send_message(
            call.message.chat.id,
            "🖥 SLH OS\n"
            "שירות פעיל, DB פעיל, LLM תקין.\n"
            "שלח /doctor לדוח מלא."
        )

    @bot.callback_query_handler(func=lambda call: call.data == "refresh_dashboard")
    def refresh_dashboard(call):
        bot.answer_callback_query(call.id, "🔄 עודכן")
        send_dashboard(call.message.chat.id, str(call.from_user.id))

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
