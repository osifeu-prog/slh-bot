import os, subprocess, time
from telebot import TeleBot
import sqlite3

def register_doctor_handlers(bot: TeleBot):
    @bot.message_handler(commands=['doctor'])
    def doctor(m):
        msg = bot.reply_to(m, "🩺 מריץ אבחון מערכת מקיף...")
        report = generate_health_report(bot)
        bot.edit_message_text(report, m.chat.id, msg.message_id)


def generate_health_report(bot: TeleBot) -> str:
    checks = {}
    try:
        me = bot.get_me()
        checks['Bot'] = f"🟢 @{me.username}"
    except:
        checks['Bot'] = "🔴 לא מחובר"
    railway_status = "🟢 מחובר"
    try:
        if os.path.exists("/app/state"):
            railway_status += " (volume תקין)"
        else:
            railway_status += " (ללא volume)"
    except:
        railway_status = "🔴 שגיאה"
    checks['Railway'] = railway_status
    checks['Git'] = "⚪️ לא נבדק (Railway container)"

    db_path = "slh_state.db"
    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            conn.execute("SELECT 1")
            conn.close()
            checks['DB'] = "🟢 פעיל"
        except:
            checks['DB'] = "🔴 גישה נכשלה"
    else:
        checks['DB'] = "🟡 קובץ לא נמצא"
    checks['Volume'] = "⚪ לא נבדק (Railway runtime)"
    try:
        from handlers.llm_handler import is_llm_available
        checks['LLM API'] = "🟢 זמין" if is_llm_available() else "🟡 לא זמין"
    except:
        checks['LLM API'] = "⚪️ לא נבדק"
    checks['Dashboard'] = "⚪️ לא נבדק (שירות נפרד)"

    handlers_count = len(bot.message_handlers) if hasattr(bot, 'message_handlers') else 0
    checks['Handlers'] = f"{handlers_count} רשומים"
    checks['Agents'] = "⚪️ לא נבדק"
    checks['Lock'] = "⚪️ לא נבדק"
    checks['Health'] = "⚪️ לא נבדק"
    lines = ["🩺 SLH HEALTH REPORT", ""]
    for key, val in checks.items():
        lines.append(f"{key}: {val}")
    lines.append("")
    lines.append("המלצה:")
    critical = [
        checks.get("Bot"),
        checks.get("DB"),
        
        checks.get("LLM API")
    ]

    if any("🔴" in str(x) for x in critical):
        lines.append("❌ יש בעיות ברכיב קריטי")
    else:
        lines.append("✅ Safe to deploy / operate")
    return "\n".join(lines)
