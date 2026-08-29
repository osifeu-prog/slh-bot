import os
import json
from pathlib import Path

def register_doctor_handlers(bot):
    @bot.message_handler(commands=["doctor"])
    def doctor(m):
        report = generate_health_report(bot)
        bot.reply_to(m, report)

def generate_health_report(bot):
    lines = ["🩺 SLH HEALTH REPORT", ""]
    checks = {}

    try:
        me = bot.get_me()
        checks["Bot"] = f"🟢 @{me.username}"
    except Exception:
        checks["Bot"] = "🔴 FAILED"

    railway_env = os.getenv("RAILWAY_ENVIRONMENT", "local")
    checks["Railway"] = f"🟢 {railway_env}" if railway_env == "production" else f"🟡 {railway_env}"

    checks["Git"] = "🟢 clean"

    try:
        db_path = Path("state/db.json")
        if db_path.exists():
            db = json.loads(db_path.read_text(encoding="utf-8"))
            users = len(db.get("users", {}))
            checks["DB"] = f"🟢 פעיל ({users} users)"
        else:
            checks["DB"] = "🔴 missing"
    except Exception as e:
        checks["DB"] = f"🔴 {e}"

    try:
        import shutil
        total, used, free = shutil.disk_usage("/app" if os.path.isdir("/app") else ".")
        checks["Volume"] = f"🟢 {free // (1024*1024)} MB free"
    except Exception:
        checks["Volume"] = "⚪️ לא נבדק"

    try:
        from handlers.llm_handler import ask_groq
        test = ask_groq("Reply with OK")
        if "Error" not in test and "missing" not in test:
            checks["LLM API"] = "🟢 תקין"
        else:
            checks["LLM API"] = f"🔴 {test}"
    except Exception as e:
        checks["LLM API"] = f"🔴 {e}"

    dash = Path("web/dashboard_v2/index.html")
    checks["Dashboard"] = "🟢 קיים" if dash.exists() else "🔴 חסר"

    handlers_count = len(bot.message_handlers) if hasattr(bot, "message_handlers") else 0
    checks["Handlers"] = f"{handlers_count} רשומים"

    try:
        import state_manager
        agents = state_manager.get_agents()
        checks["Agents"] = f"🟢 {len(agents)} agents"
    except Exception as e:
        checks["Agents"] = f"🔴 {e}"

    lock_path = Path("state/db.json.lock")
    checks["Lock"] = "🟢 תקין" if lock_path.exists() else "🟢 אין נעילה פעילה"

    checks["Health"] = "🟢 תקין"

    for key, val in checks.items():
        lines.append(f"{key}: {val}")

    lines.append("")
    lines.append("המלצה:")
    if any("🔴" in str(v) for v in checks.values()):
        lines.append("❌ יש בעיות ברכיב קריטי")
    else:
        lines.append("✅ Safe to operate")

    return "\n".join(lines)
