import json

def init(bot):
    @bot.message_handler(commands=['start'])
    def send_welcome(message):
        uid = str(message.chat.id)
        name = ""
        try:
            with open("db.json") as f:
                db = json.load(f)
            if uid in db.get("students", {}):
                name = db["students"][uid].get("name", "")
        except:
            pass
        msg = "🌟 **ברוכים הבאים ל-SLH Learning!** 🌟\n\n"
        if name:
            msg = f"נעים לראותך שוב, {name}!\n\n" + msg
        msg += "🎯 **הצעדים הראשונים:**\n"
        msg += "1️⃣ /join – הרשמה\n"
        msg += "2️⃣ /courses – צפייה בקורס\n"
        msg += "3️⃣ /project create – פרויקט אישי\n"
        msg += "4️⃣ /project task add – הוספת משימות\n"
        msg += "5️⃣ /myprogress – מעקב התקדמות\n"
        msg += "6️⃣ /referral – הזמנת חברים\n\n"
        msg += "👥 **בואו נבנה יחד!**"
        bot.reply_to(message, msg, parse_mode="Markdown")

    @bot.message_handler(commands=['admin'])
    def admin_panel(message):
        msg = "🔧 **ADMIN CONTROL PANEL**\n\n"
        msg += "📊 DIAGNOSTICS:\n"
        msg += "/test — Run full system diagnostic\n"
        msg += "/test_agents — Quick agent self-test\n"
        msg += "/status — System status\n"
        msg += "/health — Health check\n\n"
        msg += "🤖 AGENTS:\n"
        msg += "/agents — List all agents\n"
        msg += "/agent_create [name] — Create new agent\n"
        msg += "/agentstate <prefix> <state> — Change agent state\n"
        msg += "/sendagent <prefix> <msg> — Send message to agent\n"
        msg += "/inbox <prefix> — Check agent inbox\n\n"
        msg += "🗳️ VOTING:\n"
        msg += "/vote — Create vote\n"
        msg += "/results — See results\n\n"
        msg += "💰 REVENUE:\n"
        msg += "/revenue — Revenue status\n\n"
        msg += "🔄 SYSTEM:\n"
        msg += "/backup — Git backup now\n"
        msg += "/restart — Restart bot\n"
        msg += "/logs <n> — Last N log lines\n"
        msg += "/clean — Clean temp files\n\n"
        msg += "📈 ANALYTICS:\n"
        msg += "/audit — Audit log\n"
        msg += "/memory — Memory status\n"
        msg += "/debug — Container debug info\n"
        msg += "/termux — Show Termux status\n"
        msg += "/deploy — Trigger Railway deploy\n"
        msg += "/errors — Show recent errors\n"
        msg += "/plugin list — List plugins\n"
        msg += "/goal add/list — Manage goals\n"
        msg += "/exec <cmd> — Run shell command (admin)\n"
        msg += "/termlog — Show Termux logs (admin)\n"
        msg += "/rlogs — Railway logs (admin)\n"
        msg += "/disk — Disk usage\n"
        msg += "/sysinfo — System resources"
        bot.reply_to(message, msg, parse_mode="Markdown")
