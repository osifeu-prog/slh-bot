def register_logo_handler(bot):
    @bot.message_handler(commands=['logo', 'brand'])
    def logo_cmd(msg):
        with open("branding/SLH_LOGO.txt", "r", encoding="utf-8") as f:
            bot.reply_to(msg, f"<pre>{f.read()}</pre>", parse_mode="HTML")
