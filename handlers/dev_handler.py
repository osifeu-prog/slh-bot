def register(bot):
    @bot.message_handler(commands=['dev_help'])
    def dev_help(m):
        from core.authority import get_role
        uid = str(m.from_user.id)
        role = get_role(uid)
        if role not in ("DEVELOPER", "ADMIN", "OWNER"):
            bot.reply_to(m, "⛔ Developer access required.")
            return
        lines = [
            "🛠 SLH OS Developer — Telegram workflow",
            "",
            f"Role: {role}",
            "",
            "READ / AUDIT:",
            "/e whoami",
            "/e pwd",
            "/e cat <path>",
            "/e grep <pattern> <path>",
            "/e find <path> ...",
            "/e settlement_status",
            "",
            "AGENT:",
            "/agents",
            "/inbox <agent>",
            "/sendagent <agent> <message>",
            "",
            "ACCESS:",
            "/dev_request  → request Developer role",
            "/dev_requests → OWNER: pending requests",
            "/execr <command> → request OWNER approval",
            "",
            "DEVELOPER LAB:",
            "/dev_read <path>",
            "/dev_write <path> <summary>\\n<complete file content>",
            "/dev_lab_preview <request_id>",
            "/dev_lab_status <request_id>",
            "/dev_ci <request_id>",
            "",
            "NATURAL-LANGUAGE READ-ONLY:",
            "/dev בדוק את Investor Overview שהגדרנו",
            "/dev בדוק את הפקודות וה-collisions",
            "Unrecognized /dev intents are not executed.",
            "",
            "Your code changes become proposals. OWNER approval creates a GitHub branch + PR.",
            "CI runs on the PR. Merge/deploy remain separately controlled.",
        ]
        bot.reply_to(m, "\n".join(lines))

    @bot.message_handler(commands=['dev'])
    def dev_menu(msg):
        from core.authority import get_role
        from core.developer_intent import inspect

        uid = str(msg.from_user.id)
        role = get_role(uid)
        if role not in ("DEVELOPER", "ADMIN", "OWNER"):
            bot.reply_to(msg, "⛔ Developer access required.")
            return

        parts = (msg.text or "").split(maxsplit=1)
        if len(parts) == 1:
            text = """🛠 SLH OS Developer Dashboard

/dev בדוק את Investor Overview
/dev בדוק את הפקודות וה-collisions

/system – System overview
/status – Railway status
/logs <n> – Recent logs
/deploy – Trigger deploy
/test – Run self-test

📁 Project: github.com/osifeu-prog/slh-bot
📊 Runtime command evidence: use /dev בדוק את הפקודות
📄 Docs: DEVELOPER_GUIDE.md

Read-only intent checks do not mutate DB, wallets, settlement, or production.
"""
            bot.reply_to(msg, text)
            return

        try:
            result = inspect(parts[1], bot)
            if result["intent"] == "investor_overview":
                checks = result["checks"]
                lines = [
                    "🔎 Investor Overview — read-only inspection",
                    f"Status: {result['status']}",
                    "",
                    f"✅ canonical investor_read_model: {'present' if checks['canonical_read_model'] else 'missing'}",
                    f"{'✅' if checks['telegram_button_or_callback'] else '⚠️'} Telegram Investor button/callback: {'present' if checks['telegram_button_or_callback'] else 'missing'}",
                    f"{'✅' if checks['mini_app_screen'] else '⚠️'} Mini App screen=investor: {'present' if checks['mini_app_screen'] else 'missing'}",
                    f"✅ /api/v1/me: {'present' if checks['me_api'] else 'missing'}",
                    "",
                    f"Next: {result['next_step']}",
                    "Source: deployed repository files · read-only",
                ]
            else:
                lines = [
                    "🔎 Runtime command evidence — read-only",
                    f"Handlers: {result['total_handlers']}",
                    f"Registrations: {result['command_registrations']}",
                    f"Unique commands: {result['unique_commands']}",
                    f"Collisions: {result['collision_count']}",
                    f"Source: {result['source']}",
                ]
                if result["collision_count"]:
                    for command, registrations in list(result["collisions"].items())[:10]:
                        owners = ", ".join(
                            str(item.get("module") or item.get("function") or "?")
                            for item in registrations
                        )
                        lines.append(f"• {command}: {owners}")
                else:
                    lines.append("✅ No runtime command collisions detected.")
                lines.append("No dispatch or mutation was performed.")
            bot.reply_to(msg, "\n".join(lines)[:3900])
        except ValueError as exc:
            if str(exc) == "UNKNOWN_DEV_INTENT":
                bot.reply_to(
                    msg,
                    "ℹ️ /dev is read-only and intent-based.\n"
                    "Supported now:\n"
                    "• Investor Overview\n"
                    "• Runtime command / collision audit\n"
                    "Unknown requests are not executed. Use /dev_help.",
                )
            else:
                bot.reply_to(msg, f"❌ Developer inspection: {str(exc)}")
        except Exception as exc:
            bot.reply_to(msg, f"❌ Developer inspection failed safely: {type(exc).__name__}")

    @bot.message_handler(commands=['system'])
    def system(msg):
        import json
        with open('state/db.json') as f:
            d = json.load(f)
        text = f"👥 Users: {len(d.get('users',{}))}\n🤖 Agents: {len(d.get('agents',{}))}\n✅ Tasks: {len(d.get('tasks',[]))}"
        bot.reply_to(msg, text)

    print("✅ dev_handler loaded")
