import os
import json
import importlib

def register(bot, context=None):

    @bot.message_handler(commands=['recovery_verify'])
    def recovery_verify(m):
        try:
            lines = []

            lines.append("🛡 SLH RECOVERY VERIFY")
            lines.append("")
            lines.append("Mode: READ ONLY")
            lines.append("")

            # Files
            lines.append("FILES:")
            for f in [
                "state/db.json",
                "state/agents.json",
                "state/ai_health.json",
                "handlers/loader.py",
                "handlers/recovery_handler.py"
            ]:
                lines.append(
                    f"{f}: " +
                    ("OK" if os.path.exists(f) else "MISSING")
                )

            # JSON integrity
            lines.append("")
            lines.append("JSON:")
            for f in [
                "state/db.json",
                "state/agents.json",
                "state/ai_health.json"
            ]:
                try:
                    with open(f, encoding="utf-8") as x:
                        json.load(x)
                    lines.append(f"{f}: VALID")
                except Exception as e:
                    lines.append(f"{f}: ERROR {e}")

            # Agents
            try:
                with open("state/db.json", encoding="utf-8") as x:
                    d = json.load(x)

                agents = d.get("agents", {})
                active = sum(
                    1 for a in agents.values()
                    if a.get("state") == "active"
                )

                lines.append("")
                lines.append("AGENTS:")
                lines.append(f"Total: {len(agents)}")
                lines.append(f"Active: {active}")
                lines.append(f"Idle: {len(agents)-active}")

            except Exception as e:
                lines.append("Agents ERROR: " + str(e))

            # Imports
            lines.append("")
            lines.append("IMPORTS:")

            for module in [
                "handlers.loader",
                "handlers.recovery_handler"
            ]:
                try:
                    importlib.import_module(module)
                    lines.append(f"{module}: OK")
                except Exception as e:
                    lines.append(f"{module}: ERROR {e}")

            lines.append("")
            lines.append("Result: SAFE")

            bot.reply_to(m, "\n".join(lines))

        except Exception as e:
            bot.reply_to(m, "Recovery verify error: " + str(e))

    print("recovery verify loaded")
