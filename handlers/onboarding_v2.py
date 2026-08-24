from core.identity import OWNER_TELEGRAM_ID
from telebot import types
import json
from core.message_utils import safe_clip

from core.profile_manager import get_user, update_user
from core.agent_registry import create_agent
from core.identity_resolver import get_display_name
from core.invite_gate import can_start_onboarding


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


    @bot.message_handler(
        commands=["start"]
    )
    def start(m):

        user_id = str(
            m.from_user.id
        )

        user_name = (
            get_display_name(user_id, m.from_user)
            or "חבר"
        )

        db = load_db()

        is_owner = int(user_id) == int(OWNER_TELEGRAM_ID)

        is_new = (
            user_id
            not in db.get(
                "users",
                {}
            )
        )

        if not can_start_onboarding(
            is_owner=is_owner,
            is_existing_user=not is_new,
        ):
            bot.send_message(
                m.chat.id,
                "🚧 ההצטרפות לאלפא סגורה כרגע.\n"
                "נדרש Invite כדי להצטרף."
            )
            return

        if is_owner:
            text = (
                f"\u05d1\u05e8\u05d5\u05da \u05e9\u05d5\u05d1\u05da, {user_name}!\n\n"
                "\u05d0\u05e0\u05d9 \u05e8\u05d5\u05d1\u05d5\u05d8\u05d5\u05e9, \u05d4\u05e2\u05d5\u05d6\u05e8 \u05d4\u05d0\u05d9\u05e9\u05d9 \u05e9\u05dc\u05da.\n\n"
                "\U0001f451 \u05d4\u05de\u05e2\u05e8\u05db\u05ea \u05de\u05d6\u05d4\u05d4 \u05d0\u05d5\u05ea\u05da \u05db\u05d1\u05e2\u05dc\u05d9\u05dd \u05e9\u05dc SLH OS.\n"
                "\U0001f680 \u05d4-Dashboard \u05d5\u05d4\u05de\u05e2\u05e8\u05db\u05ea \u05d4\u05d0\u05d9\u05e9\u05d9\u05ea \u05e9\u05dc\u05da \u05de\u05d5\u05db\u05e0\u05d9\u05dd."
            )

            markup = types.InlineKeyboardMarkup()

            markup.add(
                types.InlineKeyboardButton(
                    "\U0001f4ca \u05d4-Dashboard \u05e9\u05dc\u05d9",
                    callback_data="goto_dashboard"
                )
            )

            markup.add(
                types.InlineKeyboardButton(
                    "\U0001f916 \u05d4\u05e1\u05d5\u05db\u05e0\u05d9\u05dd \u05e9\u05dc\u05d9",
                    callback_data="create_agent"
                )
            )

        elif is_new:

            text = (
                f"ברוך הבא, {user_name}!\n\n"
                "אני רובוטוש, העוזר האישי שלך.\n\n"
                "🚀 בוא נתחיל את ההפעלה."
            )

            markup = types.InlineKeyboardMarkup()

            markup.add(
                types.InlineKeyboardButton(
                    "🚀 כן, תתחיל אותי!",
                    callback_data="onboard_start"
                )
            )

        else:

            text = (
                f"ברוך שובך, {user_name}!\n\n"
                "ה-Dashboard שלך מחכה לך."
            )

            markup = types.InlineKeyboardMarkup()

            markup.add(
                types.InlineKeyboardButton(
                    "📊 לך ל-Dashboard",
                    callback_data="goto_dashboard"
                )
            )

            markup.add(
                types.InlineKeyboardButton(
                    "🤖 צור סוכן חדש",
                    callback_data="create_agent"
                )
            )

        bot.send_message(
        m.chat.id,
        safe_clip(text),
            reply_markup=markup
        )


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
                f"ג„¹ן¸ {e}"
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

