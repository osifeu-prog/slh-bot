def register(bot):
    @bot.message_handler(commands=['dev_help'])
    def dev_help(m):
        from core.authority import get_role, has_permission
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
            "/dev_write <path> <summary>\\n<complete file content>",
            "/dev_lab_status <request_id>",
            "/dev_ci <request_id>",
            "Your change becomes a proposal. OWNER approval creates a GitHub branch + PR.",
            "CI runs on the PR. Merge/deploy remain separately controlled.",
        ]
        bot.reply_to(m, "\n".join(lines))

    @bot.message_handler(commands=['dev'])
    def dev_menu(msg):
        text = """🛠 SLH OS Developer Dashboard

/system – System overview
/status – Railway status
/logs <n> – Recent logs
/deploy – Trigger deploy
/test – Run self-test

📁 Project: github.com/osifeu-prog/slh-bot
📊 Commands: 165 registered
📄 Docs: DEVELOPER_GUIDE.md
"""
        bot.reply_to(msg, text)

    @bot.message_handler(commands=['system'])
    def system(msg):
        import json
        with open('state/db.json') as f:
            d = json.load(f)
        text = f"👥 Users: {len(d.get('users',{}))}\n🤖 Agents: {len(d.get('agents',{}))}\n✅ Tasks: {len(d.get('tasks',[]))}"
        bot.reply_to(msg, text)

    print("✅ dev_handler loaded")
