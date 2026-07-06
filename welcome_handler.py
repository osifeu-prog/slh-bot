from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import json, os

def init(bot):
    @bot.message_handler(commands=['start'])
    def send_welcome(message):
        uid = str(message.chat.id)
        name = ""
        try:
            with open("state/db.json") as f:
                db = json.load(f)
                name = db.get("users", {}).get(uid, {}).get("name", "")
        except:
            pass

        # Logo
        try:
            with open("logo.txt") as lf:
                logo = lf.read()
            bot.send_message(message.chat.id, f"```\n{logo}\n```", parse_mode="Markdown")
        except:
            pass

        greeting = f"נעים לראותך שוב, {name}!" if name else "🌟 ברוכים הבאים ל-SLH OS!"

        # Welcome message with explanation
        welcome_text = (
            f"{greeting}\n\n"
            "📚 **מערכת הפעלה חכמה** – קורסים, סוכני AI, השקעות, וכלכלה דיגיטלית.\n"
            "👇 בחר אפשרות להתחיל:"
        )
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("📚 קורסים", callback_data="menu_courses"),
            InlineKeyboardButton("💰 השקעות", callback_data="menu_investments"),
            InlineKeyboardButton("🤖 סוכנים", callback_data="menu_agents"),
            InlineKeyboardButton("👤 פרופיל", callback_data="menu_progress"),
            InlineKeyboardButton("❓ עזרה", callback_data="menu_help"),
        )
        # Admin button only for admin IDs
        if uid in ("8789977826",):  # replace with your ID(s)
            markup.add(InlineKeyboardButton("🔧 אדמין", callback_data="menu_admin"))

        bot.send_message(message.chat.id, welcome_text, reply_markup=markup, parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("menu_"))
    def handle_menu_click(call):
        action = call.data.replace("menu_", "")
        if action == "courses":
            bot.send_message(call.message.chat.id, "📚 קורסים:\n/courses – לרשימת קורסים\n/course_slh – קורס SLH")
        elif action == "investments":
            bot.send_message(call.message.chat.id, "💰 השקעות:\n/stake – Staking\n/stake_join <amount> – הצטרף\n/pnl – PnL\n/staking_report – דו\"ח")
        elif action == "agents":
            bot.send_message(call.message.chat.id, "🤖 סוכנים:\n/agents – רשימה\n/agent_create <name> – יצירה\n/agent_submit <name> – הגשה")
        elif action == "progress":
            bot.send_message(call.message.chat.id, "👤 השתמש ב- /myprogress")
        elif action == "help":
            bot.send_message(call.message.chat.id, "❓ עזרה:\n/help – תפריט הפקודות\n/admin – לוח מנהל\n/start – התחלה")
        elif action == "admin":
            # Additional admin check
            if str(call.message.chat.id) not in ("8789977826",):
                bot.answer_callback_query(call.id, "⛔️ אין הרשאה")
                return
            bot.send_message(call.message.chat.id, "🔧 לוח מנהל:\n/admin – תפריט מלא\n/exec – הרצת פקודות\n/broadcast – שידור")
        bot.answer_callback_query(call.id)
