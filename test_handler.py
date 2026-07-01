from self_test import test_all

def init(bot):
    @bot.message_handler(commands=['self_test'])
    def self_test(m):
        if str(m.chat.id) != "8789977826":
            bot.reply_to(m, "❌ Admin only")
            return
        results = test_all()
        msg = "📊 **Self Test Results**\n" + "\n".join([f"{name}: {status}" for name, status in results])
        bot.reply_to(m, msg, parse_mode="Markdown")
