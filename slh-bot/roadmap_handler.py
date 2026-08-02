def init(bot):
    @bot.message_handler(commands=['roadmap'])
    def roadmap(m):
        try:
            with open("ROADMAP.md", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            bot.send_message(m.chat.id, f"Error reading roadmap: {e}")
            return
        for i in range(0, len(content), 3800):
            bot.send_message(m.chat.id, content[i:i+3800])
