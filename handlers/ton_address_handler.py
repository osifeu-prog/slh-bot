def register(bot):
    @bot.message_handler(commands=["ton_address"])
    def ton_address_cmd(msg):
        bot.reply_to(
            msg,
            "⛔ TON deposits are temporarily paused.\n"
            "Do not send TON or USDT for automated crediting until secure user-binding is enabled."
        )
