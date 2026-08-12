import os
import json

def register(bot, context=None):

    @bot.message_handler(commands=['recovery'])
    def recovery(m):
        try:
            lines = []

            lines.append("🛡 SLH OS RECOVERY STATUS")
            lines.append("")
            lines.append("Runtime: ONLINE")
            lines.append("")

            for f in [
                "state/db.json",
                "state/agents.json",
                "state/ai_health.json"
            ]:
                lines.append(
                    f"{f}: " +
                    ("OK" if os.path.exists(f) else "MISSING")
                )

            try:
                with open("state/db.json", encoding="utf-8") as x:
                    d = json.load(x)

                agents = d.get("agents", {})
                active = sum(
                    1 for a in agents.values()
                    if a.get("state") == "active"
                )

                lines.append("")
                lines.append(f"Agents: {len(agents)}")
                lines.append(f"Active: {active}")
                lines.append(f"Idle: {len(agents)-active}")

                users = d.get("users", {})
                lines.append("")
                lines.append(f"Users: source state/db.json ({len(users)})")

            except Exception as e:
                lines.append("State check error: " + str(e))

            lines.append("")
            lines.append("Recovery Mode: SAFE READ ONLY")

            bot.reply_to(m, "\n".join(lines))

        except Exception as e:
            bot.reply_to(m, "Recovery error: " + str(e))

    print("recovery handler loaded")
