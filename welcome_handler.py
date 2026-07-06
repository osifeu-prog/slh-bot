def init(bot):
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    import json

    @bot.message_handler(commands=['start'])
    def send_welcome(message):
        uid = str(message.chat.id)
        name = ""
        try:
            with open("state/db.json") as f:
                db = json.load(f)
                if uid in db.get("students", {}):
                    name = db["students"][uid].get("name", "")
        except:
            pass
        greeting = f"נעים לראותך שוב, {name}!" if name else "🌟 ברוכים הבאים ל-SLH Learning!"

        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("📚 קורסים", callback_data="menu_courses"),
            InlineKeyboardButton("📁 פרויקטים", callback_data="menu_projects"),
            InlineKeyboardButton("🤖 סוכנים", callback_data="menu_agents"),
            InlineKeyboardButton("👤 התקדמות שלי", callback_data="menu_progress"),
            InlineKeyboardButton("🔗 הפניה", callback_data="menu_referral"),
            InlineKeyboardButton("🛠 דמו", callback_data="menu_demo"),
            InlineKeyboardButton("❓ עזרה", callback_data="menu_help")
        )
        bot.send_message(message.chat.id, f"```\n{open('logo.txt').read()}\n```", parse_mode="Markdown")
        bot.send_message(message.chat.id, greeting, reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("menu_"))
    def handle_menu_click(call):
        action = call.data.replace("menu_", "")
        if action == "courses":
            bot.send_message(call.message.chat.id, "📚 קורסים:\n/ courses – לרשימת הקורסים\n/ join – להרשמה")
        elif action == "projects":
            bot.send_message(call.message.chat.id, "📁 פרויקטים:\n/ project create – יצירה\n/ project list – צפייה")
        elif action == "agents":
            bot.send_message(call.message.chat.id, "🤖 סוכנים:\n/ agents – רשימה\n/ agent_create [שם] – יצירה")
        elif action == "progress":
            bot.send_message(call.message.chat.id, "👤 השתמש ב- /myprogress")
        elif action == "referral":
            bot.send_message(call.message.chat.id, "🔗 השתמש ב- /referral")
        elif action == "demo":
            bot.send_message(call.message.chat.id, "🛠 השתמש ב- /demo tasks / agents / guide")
        elif action == "help":
            bot.send_message(call.message.chat.id, "❓ עזרה:\n/admin – לוח מנהל\n/start – התחלה")
        bot.answer_callback_query(call.id)
