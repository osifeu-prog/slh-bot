import json
from pathlib import Path

def register(bot, context=None):
    @bot.message_handler(commands=["health_monitor"])
    def health_monitor(m):
        db = json.loads(Path("state/db.json").read_text(encoding="utf-8"))
        checks = []
        checks.append(("Runtime", "✅" if Path("bot_gateway.py").exists() else "❌"))
        checks.append(("Wallet", "✅" if db["users"]["8789977826"]["wallet"]["credits"] == 0 else "❌"))
        checks.append(("System Services", "✅" if len(db.get("system_services", {})) == 4 else "❌"))
        checks.append(("Ledger", "✅" if db.get("ledger") else "❌"))
        checks.append(("Tasks", "✅" if len(db.get("tasks", {})) >= 8 else "❌"))
        text = "🔍 HEALTH MONITOR\n\n"
        for name, status in checks:
            text += f"{status} {name}\n"
        bot.reply_to(m, text)
