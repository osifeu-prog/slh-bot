def register(bot):
    @bot.message_handler(commands=['endday'])
    def endday(msg):
        uid = str(msg.from_user.id)
        bot.reply_to(msg, f'🌙 סוף יום, {uid}!\n\n📚 /progress\n🤖 /agents\n💰 /balance')
