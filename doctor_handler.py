import os
import json
from pathlib import Path

def register_doctor_handlers(bot):
    @bot.message_handler(commands=["doctor"])
    def doctor(m):
        from core.authority import has_permission
        uid = str(m.from_user.id)
        if not has_permission(uid, "exec.audit"):
            bot.reply_to(m, "⛔️ הרשאת אבחון מערכת מלאה נדרשת.")
            return
        report = generate_health_report(bot, uid)
        bot.reply_to(m, report)

def generate_health_report(bot, uid=None):
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

    # LLM configuration only: do not call a provider from /doctor or burn quota.
    # Keep this check aligned with system_health and the canonical provider chain.
    try:
        from system_health import get_health
        components = get_health().get("components", {})
        providers = components.get("llm_providers", {})
        configured = [name for name, ok in providers.items() if ok]
        if configured:
            checks["LLM API"] = "🟢 configured: " + ", ".join(configured)
        else:
            checks["LLM API"] = "🔴 no provider configured"
    except Exception as e:
        checks["LLM API"] = f"🔴 {type(e).__name__}"

    dash = Path("web/dashboard_v2/index.html")
    checks["Dashboard"] = "🟢 קיים" if dash.exists() else "🔴 חסר"

    handlers_count = len(bot.message_handlers) if hasattr(bot, "message_handlers") else 0
    checks["Handlers"] = f"{handlers_count} רשומים"

    try:
        import state_manager
        agents = [a for a in state_manager.get_agents().values() if a.get("state") != "archived"]
        checks["Agents"] = f"🟢 {len(agents)} agents"
    except Exception as e:
        checks["Agents"] = f"🔴 {e}"

    lock_path = Path("state/db.json.lock")
    checks["Lock"] = "🟢 תקין" if lock_path.exists() else "🟢 אין נעילה פעילה"

    checks["Health"] = "🟢 תקין"

    try:
        from core.control_center import get_infrastructure_snapshot
        infrastructure = get_infrastructure_snapshot()
        non_green = infrastructure.get("non_green", [])
        checks["Federation"] = (
            f"⚠️ {len(non_green)} application services not green"
            if non_green
            else "🟢 application services green"
        )
    except Exception:
        checks["Federation"] = "⚪️ not verified"

    for key, val in checks.items():
        lines.append(f"{key}: {val}")

    lines.append("")
    lines.append("המלצה:")
    if any("🔴" in str(v) for v in checks.values()):
        lines.append("❌ יש בעיות ברכיב קריטי")
    elif "not green" in str(checks.get("Federation", "")):
        lines.append("🟡 הבוט המרכזי נבדק; שירותי הפדרציה דורשים בדיקה.")
    elif "not verified" in str(checks.get("Federation", "")):
        lines.append("🟡 הבוט נבדק מקומית; הפדרציה לא אומתה.")
    else:
        lines.append("✅ הבוט והפדרציה ללא חריגה מדווחת.")

    return "\n".join(lines)
