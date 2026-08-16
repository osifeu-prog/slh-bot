def init(bot):
    @bot.message_handler(commands=['devsetup'])
    def devsetup(m):
        try:
            with open("SESSION_STATUS.md", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            bot.reply_to(m, f"שגיאה בקריאת SESSION_STATUS.md: {e}")
            return

        text = (
            "👨‍💻 **הצטרפות מפתח חדש ל-SLH**\n\n"
            "1️⃣ שכפל את הריפו:\n"
            "`git clone https://github.com/osifeu-prog/slh-bot.git`\n\n"
            "2️⃣ הרץ בתוך התיקייה:\n"
            "`./setup_dev_env.sh && source ~/.bashrc`\n\n"
            "3️⃣ קרא את מצב הפרויקט המלא למטה 👇\n"
        )
        bot.reply_to(m, text, parse_mode="Markdown")

        for i in range(0, len(content), 3800):
            bot.send_message(m.chat.id, content[i:i+3800])
