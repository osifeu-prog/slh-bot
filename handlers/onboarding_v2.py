from core.identity import OWNER_TELEGRAM_ID
from telebot import types
import json
from core.message_utils import safe_clip

from core.profile_manager import get_user
from core.agent_registry import create_agent
from core.identity_resolver import get_display_name


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
            "׳׳™׳"
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
            "נ ׳”-Dashboard ׳©׳׳\n\n"
            f"נ’° Credits: {credits}\n"
            f"נ“ ׳§׳•׳¨׳¡ ׳₪׳¢׳™׳: {course}\n"
            f"נ₪– ׳”׳¡׳•׳›׳ ׳™׳ ׳©׳׳: {len(owned_agents)}\n\n"
            "׳׳” ׳×׳¨׳¦׳” ׳׳¢׳©׳•׳×?"
        )

        markup = types.InlineKeyboardMarkup(
            row_width=1
        )

        markup.add(
            types.InlineKeyboardButton(
                "נ“ ׳”׳׳©׳ ׳׳§׳•׳¨׳¡",
                callback_data="continue_course"
            )
        )

        markup.add(
            types.InlineKeyboardButton(
                "נ₪– ׳¦׳•׳¨ ׳¡׳•׳›׳ ׳—׳“׳©",
                callback_data="create_agent"
            )
        )

        markup.add(
            types.InlineKeyboardButton(
                "נ“ ׳¡׳˜׳˜׳•׳¡ ׳׳¢׳¨׳›׳×",
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
            or "׳—׳‘׳¨"
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
                f"׳‘׳¨׳•׳ ׳”׳‘׳, {user_name}!\n\n"
                "׳׳ ׳™ ׳¨׳•׳‘׳•׳˜׳•׳©, ׳”׳¢׳•׳–׳¨ ׳”׳׳™׳©׳™ ׳©׳׳.\n\n"
                "נ€ ׳‘׳•׳ ׳ ׳×׳—׳™׳ ׳׳× ׳”׳”׳₪׳¢׳׳”."
            )

            markup = types.InlineKeyboardMarkup()

            markup.add(
                types.InlineKeyboardButton(
                    "נ€ ׳›׳, ׳×׳×׳—׳™׳ ׳׳•׳×׳™!",
                    callback_data="onboard_start"
                )
            )

        else:

            text = (
                f"׳‘׳¨׳•׳ ׳©׳•׳‘׳, {user_name}!\n\n"
                "׳”-Dashboard ׳©׳׳ ׳׳—׳›׳” ׳׳."
            )

            markup = types.InlineKeyboardMarkup()

            markup.add(
                types.InlineKeyboardButton(
                    "נ“ ׳׳ ׳-Dashboard",
                    callback_data="goto_dashboard"
                )
            )

            markup.add(
                types.InlineKeyboardButton(
                    "נ₪– ׳¦׳•׳¨ ׳¡׳•׳›׳ ׳—׳“׳©",
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
                    f"{get_display_name(call.from_user.id, call.from_user)}-Agent",
                    owner_id=user_id
                )

            bot.answer_callback_query(
                call.id,
                "ג… ׳”׳—׳©׳‘׳•׳ ׳”׳•׳₪׳¢׳"
            )

            bot.send_message(
                call.message.chat.id,
                "ג… ׳”׳₪׳¨׳•׳₪׳™׳ ׳©׳׳ ׳”׳•׳₪׳¢׳!\n"
                "נ₪– ׳”׳¡׳•׳›׳ ׳”׳׳™׳©׳™ ׳©׳׳ ׳׳•׳›׳.\n\n"
                "׳‘׳¨׳•׳ ׳”׳‘׳ ׳-SLH OS."
            )

            send_dashboard(
                call.message.chat.id,
                user_id
            )

        except Exception as e:

            bot.answer_callback_query(
                call.id,
                "ג ׳©׳’׳™׳׳” ׳‘׳”׳₪׳¢׳׳× ׳”׳—׳©׳‘׳•׳"
            )

            bot.send_message(
                call.message.chat.id,
                f"ג Onboarding failed: {type(e).__name__}"
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
                "נ₪– ׳”׳¡׳•׳›׳ ׳ ׳•׳¦׳¨"
            )

            bot.send_message(
                call.message.chat.id,
                "ג… ׳”׳¡׳•׳›׳ ׳ ׳•׳¦׳¨ ׳‘׳”׳¦׳׳—׳”\n"
                f"נ†” ID: {agent_id}"
            )

        except ValueError as e:

            bot.answer_callback_query(
                call.id,
                "ג ן¸ ׳”׳¡׳•׳›׳ ׳›׳‘׳¨ ׳§׳™׳™׳"
            )

            bot.send_message(
                call.message.chat.id,
                f"ג„¹ן¸ {e}"
            )

        except Exception as e:

            bot.answer_callback_query(
                call.id,
                "ג ׳©׳’׳™׳׳”"
            )

            bot.send_message(
                call.message.chat.id,
                f"ג Agent creation failed: {type(e).__name__}"
            )

