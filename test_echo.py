import telebot, time

with open("config.json") as f:
    cfg = __import__('json').load(f)

bot = telebot.TeleBot(cfg["BOT_TOKEN"])

@bot.message_handler(func=lambda m: True)
def echo(m):
    bot.reply_to(m, m.text)

print("ECHO BOT READY")
bot.infinity_polling(skip_pending=True, timeout=10, long_polling_timeout=10)
