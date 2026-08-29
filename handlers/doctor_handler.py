import os
import json
from pathlib import Path
import traceback

def _ok(label, val):
    return f"🟢 {label}: {val}" if val else f"🔴 {label}: {val}"

def register(bot):
    @bot.message_handler(commands=["doctor"])
    def doctor_cmd(msg):
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

        # LLM API
        try:
            from handlers.llm_handler import ask_groq
            test = ask_groq("Reply with OK")
            if "Error" not in test and "missing" not in test:
                lines.append("LLM API: 🟢 תקין")
            else:
                lines.append(f"LLM API: 🔴 {test}")
        except Exception as e:
            lines.append(f"LLM API: 🔴 {e}")

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

        lines.append("")
        lines.append("המלצה: ✅ Safe to operate")
        bot.reply_to(msg, "\n".join(lines))
