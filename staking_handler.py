def register_staking_handlers(bot):
    @bot.message_handler(commands=['stake'])
    def stake(m):
        bot.send_message(m.chat.id, "⚠️ Staking module under construction.")

    @bot.message_handler(commands=['stake_join'])
    def stake_join(m):
        bot.send_message(m.chat.id, "⚠️ Staking join module under construction.")

    @bot.message_handler(commands=['staking_report'])
    def staking_report(m):
        bot.send_message(m.chat.id, "⚠️ Staking report module under construction.")
