def register(bot):
    print("✅ voting_handler placeholder loaded")
    @bot.message_handler(commands=['vote'])
    def vote(msg):
        bot.reply_to(msg, "מערכת הצבעות בבניה")
