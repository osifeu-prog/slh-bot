from core import profile_manager
from core.authority import get_visible_agents, normalize_uid
from telebot import types
import json


def register(bot):
    @bot.message_handler(commands=["dashboard"])
    def dashboard(m):
        try:
            with open("state/db.json", encoding="utf-8") as f:
                d = json.load(f)
        except Exception:
            d = {}

        user_id = normalize_uid(m.from_user.id)
        user = d.get("users", {}).get(user_id, {})

        balance = profile_manager.get_balance(user_id)
        course = user.get("academy", {}).get("active_course", "אין")
        visible_agents = get_visible_agents(user_id, d.get("agents", {}))
        agent_count = len(visible_agents)

        text = (
            f"🌟 ה-Dashboard שלך\n\n"
            f"💰 יתרה: {balance} SLH\n"
            f"📚 קורס פעיל: {course}\n"
            f"🤖 הסוכנים שלך: {agent_count}\n"
            f"🎯 משימה מומלצת: סיים שיעור 1 בביטקוין\n\n"
            f"מה תרצה לעשות?"
        )

        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("📚 המשך קורס", callback_data="continue_course"))
        markup.add(types.InlineKeyboardButton("🤖 צור סוכן חדש", callback_data="create_agent"))
        markup.add(types.InlineKeyboardButton("📊 סטטוס מערכת", callback_data="system_status"))

        bot.send_message(m.chat.id, text, reply_markup=markup)
