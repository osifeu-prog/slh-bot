from core.authority import is_owner

def register(bot):
    @bot.message_handler(commands=['dev'])
    def dev_menu(msg):
        if not is_owner(str(msg.from_user.id)):
            bot.reply_to(msg, "⛔ Developer dashboard is owner-only.")
            return
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
        if not is_owner(str(msg.from_user.id)):
            bot.reply_to(msg, "⛔ System diagnostics are owner-only.")
            return
        import json
        with open('state/db.json') as f:
            d = json.load(f)
        text = f"👥 Users: {len(d.get('users',{}))}\n🤖 Agents: {len(d.get('agents',{}))}\n✅ Tasks: {len(d.get('tasks',[]))}"
        bot.reply_to(msg, text)

    print("✅ dev_handler loaded")
