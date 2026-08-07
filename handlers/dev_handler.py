def register(bot):
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
