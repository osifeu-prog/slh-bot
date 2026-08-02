from telebot import TeleBot, types


def init(bot: TeleBot):

    @bot.message_handler(commands=['guide'])
    def guide(message):

        markup = types.InlineKeyboardMarkup(row_width=2)

        buttons = [
            ("📚 לימודים", "guide_courses"),
            ("🤖 AI Agents", "guide_agents"),
            ("📋 משימות", "guide_tasks"),
            ("💰 כלכלה", "guide_economy"),
            ("🏦 Staking", "guide_staking"),
            ("🛒 Marketplace", "guide_market"),
            ("📊 דוחות", "guide_reports"),
            ("🩺 מערכת", "guide_system"),
        ]

        for text, callback in buttons:
            markup.add(types.InlineKeyboardButton(
                text,
                callback_data=callback
            ))

        bot.send_message(
            message.chat.id,
            """
📘 SLH GUIDE

ברוכים הבאים ל-SLH OS 🚀

מערכת הפעלה חכמה הכוללת:

🎓 למידה
🤖 סוכני AI
📋 ניהול משימות
💰 כלכלה דיגיטלית
🏦 Staking
🛒 Marketplace
📊 דוחות
🩺 בדיקות מערכת

בחר תחום כדי להתחיל 👇
""",
            reply_markup=markup
        )


    @bot.callback_query_handler(
        func=lambda call: call.data.startswith("guide_")
    )
    def guide_menu(call):

        pages = {

            "courses":
            "📚 לימודים\n\n/courses\n/start_course <id>\n/myprogress",

            "agents":
            "🤖 AI Agents\n\n/agents\n/agent_create <name>\n/sendagent",

            "tasks":
            "📋 משימות\n\n/task\n/project\n/complete",

            "economy":
            "💰 כלכלה\n\n/balance\n/buy\n/pay",

            "staking":
            "🏦 Staking\n\n/stake\n/stake_join\n/staking_report",

            "market":
            "🛒 Marketplace\n\n/market\n/market_search",

            "reports":
            "📊 דוחות\n\n/report\n/myreport\n/progress",

            "system":
            "🩺 מערכת\n\n/doctor\n/help\n/ask <שאלה>",
        }

        key = call.data.replace("guide_", "")

        bot.answer_callback_query(call.id)

        bot.edit_message_text(
            pages.get(key, "❓ לא נמצא"),
            call.message.chat.id,
            call.message.message_id
        )
