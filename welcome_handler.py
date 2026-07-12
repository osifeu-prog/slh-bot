import telebot
from telebot import types

def init(bot):
    @bot.message_handler(commands=['start'])
    def start(m):
        try:
            with open("logo.txt", "r", encoding="utf-8") as lf:
                logo = lf.read()
            bot.send_message(m.chat.id, f"```\n{logo}\n```", parse_mode="Markdown")
        except Exception as e:
            print("logo error:", e)
        markup = types.InlineKeyboardMarkup(row_width=2)
        buttons = [
            ("📚 קורסים", "start_courses"),
            ("🤖 סוכנים", "start_agents"),
            ("💰 יתרה", "start_balance"),
            ("📘 עזרה", "start_help"),
            ("❓ שאלה", "start_ask"),
            ("🛠 אדמין", "start_admin")
        ]
        for text, callback in buttons:
            markup.add(types.InlineKeyboardButton(text, callback_data=callback))
        text = """**ברוך הבא ל-SLH OS!** 🚀

מערכת הפעלה חכמה – קורסים, סוכני AI, השקעות, וכלכלה דיגיטלית.

✅ **הכל כבר פה** – אין צורך להמציא כלום.
✅ **התחל** בכפתורים למטה, או שלח /help לכל הפקודות.

💡 **טיפ**: /ask <שאלה> – אני אעזור לך."""
        bot.send_message(m.chat.id, text, parse_mode="Markdown", reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('start_'))
    def start_callback(call):
        mapping = {
            "courses": "📚 קורסים זמינים – /courses",
            "agents": "🤖 סוכנים – /agents",
            "balance": "💰 יתרה – /balance",
            "help": "📘 עזרה – /help",
            "ask": "❓ שלח /ask <שאלה>",
            "admin": "🛠 אדמין – /admin"
        }
        key = call.data.replace('start_', '')
        bot.answer_callback_query(call.id)
        bot.edit_message_text(
            mapping.get(key, "❓ בחר אפשרות"),
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="Markdown"
        )
