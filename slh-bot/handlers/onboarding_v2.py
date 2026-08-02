from telebot import types
import json

from core.profile_manager import get_user
from core.agent_registry import create_agent


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
            text,
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
            m.from_user.first_name
            or "חבר"
        )

        db = load_db()

        is_new = (
            user_id
            not in db.get(
                "users",
                {}
            )
        )

        if is_new:

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
            text,
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

            get_user(
                user_id
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
                    f"{call.from_user.first_name or 'User'}-Agent",
                    owner_id=user_id
                )

            bot.answer_callback_query(
                call.id,
                "✅ החשבון הופעל"
            )

            bot.send_message(
                call.message.chat.id,
                "✅ הפרופיל שלך הופעל!\n"
                "🤖 הסוכן האישי שלך מוכן.\n\n"
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
                f"{call.from_user.first_name or 'User'}-Agent",
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
                f"ℹ️ {e}"
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
