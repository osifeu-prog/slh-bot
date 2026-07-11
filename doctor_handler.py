import os, subprocess, time
from telebot import TeleBot
from system_health import check_system_health
from slh_lock import is_locked
import sqlite3

def register_doctor_handlers(bot: TeleBot):
    @bot.message_handler(commands=['doctor'])
    def doctor(m):
        msg = bot.reply_to(m, "🩺 מריץ אבחון מערכת מקיף...")
        report = generate_health_report(bot)
        bot.edit_message_text(report, m.chat.id, msg.message_id, parse_mode="Markdown")

def generate_health_report(bot: TeleBot) -> str:
    checks = {}

    # 1. Bot
    try:
        me = bot.get_me()
        checks['Bot'] = f"🟢 @{me.username}"
    except:
        checks['Bot'] = "🔴 לא מחובר"

    # 2. Railway
    railway_status = "🟢 מחובר"
    try:
        if os.path.exists("/app/state"):
            railway_status += " (volume תקין)"
        else:
            railway_status += " (ללא volume)"
    except:
        railway_status = "🔴 שגיאה"
    checks['Railway'] = railway_status

    # 3. Git
    try:
        result = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, cwd="/app")
        if result.returncode == 0:
            if result.stdout.strip():
                checks['Git'] = "🟡 שינויים לא שמורים"
            else:
                checks['Git'] = "🟢 נקי"
        else:
            checks['Git'] = "🔴 פקודה נכשלה"
    except:
        checks['Git'] = "🔴 git לא זמין"

    # 4. Database
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

    # 5. Volume
    if os.path.exists("/app/state"):
        checks['Volume'] = "🟢 מחובר"
    else:
        checks['Volume'] = "🔴 לא מחובר"

    # 6. LLM API
    try:
        from llm_handler import is_llm_available
        if is_llm_available():
            checks['LLM API'] = "🟢 זמין"
        else:
            checks['LLM API'] = "🟡 לא זמין"
    except:
        checks['LLM API'] = "⚪️ לא נבדק"

    # 7. Dashboard
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        result = s.connect_ex(('localhost', 8080))
        s.close()
        if result == 0:
            checks['Dashboard'] = "🟢 רץ"
        else:
            checks['Dashboard'] = "🔴 לא מאזין"
    except:
        checks['Dashboard'] = "⚪️ לא נבדק"

    # 8. Handlers & Agents
    handlers_count = len(bot.message_handlers) if hasattr(bot, 'message_handlers') else 0
    agents_count = 0
    try:
        from internal_agent import list_agents
        agents_count = len(list_agents())
    except:
        pass
    checks['Handlers'] = f"{handlers_count} רשומים"
    checks['Agents'] = f"{agents_count} פעילים"

    # 9. Lock
    if is_locked():
        checks['Lock'] = "🟢 נעול"
    else:
        checks['Lock'] = "🔴 לא נעול"

    # 10. System Health
    try:
        health = check_system_health()
        if health:
            checks['Health'] = "🟢 OK"
        else:
            checks['Health'] = "🔴 בעיה"
    except:
        checks['Health'] = "⚪️ לא נבדק"


    lines = ["*🩺 SLH HEALTH REPORT*", ""]
    for key, val in checks.items():
        lines.append(f"{key}: {val}")
    lines.append("")
    lines.append("*המלצה:*")
    if "🔴" in str(checks.values()):
        lines.append("❌ יש בעיות – בדוק את הרכיבים באדום")
    else:
        lines.append("✅ Safe to deploy / operate")
    return "\n".join(lines)
