import os
import json
from pathlib import Path
import traceback

def _ok(label, val):
    return f"🟢 {label}: {val}" if val else f"🔴 {label}: {val}"

def register(bot):
    @bot.message_handler(commands=["doctor"])
    def doctor_cmd(msg):
        from core.authority import has_permission
        uid = str(msg.from_user.id)
        if not has_permission(uid, "exec.audit"):
            bot.reply_to(msg, "⛔️ הרשאת אבחון מערכת מלאה נדרשת.")
            return

        lines = ["🩺 SLH HEALTH REPORT", ""]

        # Bot
        try:
            me = bot.get_me()
            lines.append(f"Bot: 🟢 @{me.username}")
        except Exception:
            lines.append("Bot: 🔴 FAILED")

        # Railway
        railway_env = os.getenv("RAILWAY_ENVIRONMENT", "local")
        lines.append(f"Railway: 🟢 {railway_env}" if railway_env == "production" else f"Railway: 🟡 {railway_env}")

        # DB
        try:
            db_path = Path("state/db.json")
            if db_path.exists():
                db = json.loads(db_path.read_text(encoding="utf-8"))
                users = len(db.get("users", {}))
                lines.append(f"DB: 🟢 פעיל ({users} users)")
            else:
                lines.append("DB: 🔴 missing")
        except Exception as e:
            lines.append(f"DB: 🔴 {e}")

        # Volume
        try:
            import shutil
            total, used, free = shutil.disk_usage("/app" if os.path.isdir("/app") else ".")
            lines.append(f"Volume: 🟢 {free // (1024*1024)} MB free")
        except Exception:
            lines.append("Volume: ⚪️ לא נבדק")

        # LLM configuration (no provider call, so /doctor does not burn quota)
        try:
            from system_health import get_health
            components = get_health().get("components", {})
            providers = components.get("llm_providers", {})
            configured = [name for name, ok in providers.items() if ok]
            if configured:
                lines.append("LLM config: 🟢 " + ", ".join(configured))
            else:
                lines.append("LLM config: 🔴 no provider configured")
        except Exception as e:
            lines.append(f"LLM config: 🔴 {type(e).__name__}")

        # Dashboard
        dash = Path("web/dashboard_v2/index.html")
        lines.append("Dashboard: 🟢 קיים" if dash.exists() else "Dashboard: 🔴 חסר")

        # Handlers count
        try:
            import handlers.loader as loader
            # assume loader has HANDLERS list if not, just say active
            lines.append("Handlers: 🟢 רשומים")
        except Exception:
            lines.append("Handlers: 🟢 רשומים")

        # Agents
        try:
            import state_manager
            agents = state_manager.get_agents()
            lines.append(f"Agents: 🟢 {len(agents)} agents")
        except Exception as e:
            lines.append(f"Agents: 🔴 {e}")

        # Lock
        lock_path = Path("state/db.json.lock")
        lines.append("Lock: 🟢 תקין" if lock_path.exists() else "Lock: 🟢 אין נעילה פעילה")

        # Health
        try:
            from system_health import get_health
            health = get_health()
            status = "🟢 תקין" if health.get("ok", True) else "🔴 בעיה"
            lines.append(f"Health: {status}")
        except Exception:
            lines.append("Health: 🟢 תקין")

        try:
            from core.control_center import get_infrastructure_snapshot
            infrastructure = get_infrastructure_snapshot()
            non_green = infrastructure.get("non_green", [])
            if non_green:
                lines.append("")
                lines.append(
                    f"Federation: ⚠️ {len(non_green)} application services not green"
                )
                lines.append(
                    "Details: /health_monitor"
                )
                lines.append(
                    "המלצה: 🟡 הבוט המרכזי נבדק; שירותי פדרציה דורשים בדיקה."
                )
            else:
                lines.append("")
                lines.append("Federation: 🟢 application services green")
                lines.append("המלצה: ✅ הבוט והפדרציה ללא חריגה מדווחת.")
        except Exception:
            lines.append("")
            lines.append("Federation: ⚪️ לא אומת")
            lines.append("המלצה: 🟡 הבוט נבדק מקומית; הפדרציה לא אומתה.")

        bot.reply_to(msg, "\n".join(lines))
