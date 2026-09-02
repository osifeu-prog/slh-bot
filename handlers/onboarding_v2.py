from core.identity import OWNER_TELEGRAM_ID
from telebot import types
import json
from core.message_utils import safe_clip

from core.profile_manager import get_user, update_user
from core.agent_registry import create_agent
from core.identity_resolver import get_display_name
from core.invite_gate import can_start_onboarding




def load_branding():
    try:
        from datetime import datetime
        now = datetime.now()
        date_str = now.strftime("%d/%m/%Y %H:%M")
        logo = (
            'בס"ד\n'
            "███████╗██╗     ██╗  ██╗\n"
            "██╔════╝██║     ██║  ██║\n"
            "███████╗██║     ███████║\n"
            "╚════██║██║     ██╔══██║\n"
            "███████║███████╗██║  ██║\n"
            "╚══════╝╚══════╝╚═╝  ╚═╝\n\n"
            "SLH SYSTEM\n"
            "Smart Layer Hub\n"
            "🌟 רובוטוש\n"
            "🆔 972500000001\n"
            "🔗 BRIDGE: PC_Osif2 (online)\n"
            f"Updated: {date_str}"
        )
        return logo
    except Exception:
        return ""

def register(bot):

    def load_db():
        try:
            with open(
                "state/db.json",
                "r",
                encoding="utf-8"
            ) as f:
                return json.load(f)
        except Exception:
            return {
                "users": {},
                "agents": {}
            }


    def send_dashboard(chat_id, user_id):

        db = load_db()

        user = db.get(
            "users",
            {}
        ).get(
            str(user_id),
            {}
        )

        wallet = user.get(
            "wallet",
            {}
        )

        credits = wallet.get(
            "credits",
            0
        )

        course = user.get(
            "active_course",
            "אין"
        )

        owned_agents = []

        for agent in db.get(
            "agents",
            {}
        ).values():

            if (
                isinstance(agent, dict)
                and str(
                    agent.get(
                        "owner_id",
                        ""
                    )
                ) == str(user_id)
            ):
                owned_agents.append(agent)

        text = (
            "🌟 ה-Dashboard שלך\n\n"
            f"💰 Credits: {credits}\n"
            f"📚 קורס פעיל: {course}\n"
            f"🤖 הסוכנים שלך: {len(owned_agents)}\n\n"
            "מה תרצה לעשות?"
        )

        markup = types.InlineKeyboardMarkup(
            row_width=1
        )

        markup.add(
            types.InlineKeyboardButton(
                "📚 המשך לקורס",
                callback_data="continue_course"
            )
        )

        markup.add(
            types.InlineKeyboardButton(
                "🤖 צור סוכן חדש",
                callback_data="create_agent"
            )
        )

        markup.add(
            types.InlineKeyboardButton(
                "📊 סטטוס מערכת",
                callback_data="system_status"
            )
        )

        bot.send_message(
        chat_id,
        safe_clip(text),
            reply_markup=markup
        )


    @bot.message_handler(commands=["start"])
    def start(m):
        user_id = str(m.from_user.id)
        user_name = get_display_name(user_id, m.from_user) or "חבר"
        db = load_db()
        is_owner = int(user_id) == int(OWNER_TELEGRAM_ID)
        is_new = user_id not in db.get("users", {})

        if not can_start_onboarding(is_owner=is_owner, is_existing_user=not is_new):
            bot.send_message(m.chat.id, "🚧 ההצטרפות לאלפא סגורה כרגע.\nנדרש Invite כדי להצטרף.")
            return

        parts = (m.text or "").split(maxsplit=1)
        if is_new and len(parts) > 1 and parts[1].startswith("ref_"):
            ref_uid = parts[1][4:].strip()
            if ref_uid and ref_uid != user_id:
                update_user(user_id, {"referral": {"referred_by": ref_uid}})

        from datetime import datetime
        now = datetime.now().strftime("%d/%m/%Y %H:%M")
        user_wallet = db.get("users", {}).get(user_id, {}).get("wallet", {})
        credits = user_wallet.get("credits", 0)
        staked = user_wallet.get("staked", 0)

        if is_owner:
            branding = load_branding()
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
                f"📎 קישור ההזמנה האישי שלך:\n"
                f"https://t.me/Me_ad_main_bot?start=ref_{user_id}"
            )
        else:
            branding = load_branding()
            try:
                bot.send_message(m.chat.id, f"<pre>{branding}</pre>", parse_mode="HTML")
            except Exception:
                pass
            text = (
                f"ברוך הבא, {user_name}!\n\n"
                f"📅 {now}\n"
                f"👤 משתמש: {user_name}\n"
                f"💰 יתרה: {credits}\n"
                f"🔒 סטייקינג: {staked}\n\n"
                "אני רובוטוש, העוזר האישי שלך.\n"
                "כדי להתחיל, השתמש בפקודות הבאות:\n"
                "/join – הרשמה\n"
                "/dashboard – לוח אישי\n"
                "/help – עזרה\n\n"
                "🔗 הצטרף לקבוצת העדכונים הרשמית:\n"
                "https://t.me/+9VUA_6jMyQcxMGVk\n\n"
                f"📎 קישור ההזמנה האישי שלך:\n"
                f"https://t.me/Me_ad_main_bot?start=ref_{user_id}"
            )

        bot.send_message(m.chat.id, text)
    @bot.callback_query_handler(
        func=lambda call:
        call.data == "onboard_start"
    )
    def onboard_start(call):

        user_id = str(
            call.from_user.id
        )

        try:

            existing_user = get_user(
                user_id
            )

            is_owner = int(user_id) == int(OWNER_TELEGRAM_ID)

            if not can_start_onboarding(
                is_owner=is_owner,
                is_existing_user=existing_user is not None,
            ):
                bot.answer_callback_query(
                    call.id,
                    "🚧 ההצטרפות לאלפא סגורה כרגע."
                )
                return


            user_name = get_display_name(
                call.from_user.id,
                call.from_user
            )

            update_user(
                user_id,
                {
                    "role": "student",
                    "joined": True,
                    "permissions": [],
                    "name": user_name,
                    "display_name": user_name,
                }
            )

            db = load_db()

            owned_agents = []

            for agent in db.get(
                "agents",
                {}
            ).values():

                if (
                    isinstance(agent, dict)
                    and str(
                        agent.get(
                            "owner_id",
                            ""
                        )
                    ) == user_id
                ):

                    owned_agents.append(
                        agent
                    )

            if not owned_agents:

                create_agent(
                    f"{get_display_name(call.from_user.id, call.from_user)}-Agent",
                    owner_id=user_id
                )

            bot.answer_callback_query(
                call.id,
                "✅ החשבון הופעל"
            )

            bot.send_message(
                call.message.chat.id,
                "✅ הפרופיל שלך הופעל!\n"
                "הסוכן האישי שלך מוכן.\n\n"
                "ברוך הבא ל-SLH OS."
            )

            send_dashboard(
                call.message.chat.id,
                user_id
            )

        except Exception as e:

            bot.answer_callback_query(
                call.id,
                "❌ שגיאה בהפעלת החשבון"
            )

            bot.send_message(
                call.message.chat.id,
                f"❌ Onboarding failed: {type(e).__name__}"
            )


    @bot.callback_query_handler(
        func=lambda call:
        call.data == "continue_course"
    )
    def continue_course(call):
        bot.answer_callback_query(call.id, "📚 המשך לקורס")
        bot.send_message(
            call.message.chat.id,
            "📚 הקורס הפעיל שלך: bitcoin_mastery\n"
            "שלח /lesson bitcoin_mastery 1 כדי להתחיל."
        )

    @bot.callback_query_handler(
        func=lambda call:
        call.data == "system_status"
    )
    def system_status(call):
        bot.answer_callback_query(call.id, "📊 סטטוס מערכת")
        bot.send_message(
            call.message.chat.id,
            "🖥 SLH OS\n"
            "שירות פעיל, DB פעיל, LLM תקין.\n"
            "שלח /doctor לדוח מלא."
        )

    @bot.callback_query_handler(
        func=lambda call:
        call.data == "goto_dashboard"
    )
    def goto_dashboard(call):

        bot.answer_callback_query(
            call.id
        )

        send_dashboard(
            call.message.chat.id,
            str(
                call.from_user.id
            )
        )


    @bot.callback_query_handler(
        func=lambda call:
        call.data == "create_agent"
    )
    def create_agent_callback(call):

        user_id = str(
            call.from_user.id
        )

        try:

            agent_id, agent = create_agent(
                f"{get_display_name(call.from_user.id, call.from_user)}-Agent",
                owner_id=user_id
            )

            bot.answer_callback_query(
                call.id,
                "🤖 הסוכן נוצר"
            )

            bot.send_message(
                call.message.chat.id,
                "✅ הסוכן נוצר בהצלחה\n"
                f"🆔 ID: {agent_id}"
            )

        except ValueError as e:

            bot.answer_callback_query(
                call.id,
                "⚠️ הסוכן כבר קיים"
            )

            bot.send_message(
                call.message.chat.id,
                f"⚠️ {e}"
            )

        except Exception as e:

            bot.answer_callback_query(
                call.id,
                "❌ שגיאה"
            )

            bot.send_message(
                call.message.chat.id,
                f"❌ Agent creation failed: {type(e).__name__}"
            )

