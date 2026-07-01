import telebot
bot = telebot.TeleBot('YOUR_TOKEN_HERE')  # שנה לטוקן שלך

@bot.message_handler(commands=['start'])
def start(m):
    bot.reply_to(m, '✅ Minimal Bot OK')

@bot.message_handler(commands=['leaderboard'])
def leaderboard(m):
    bot.reply_to(m, '🏆 Leaderboard Test')

print('Minimal Bot started')
bot.infinity_polling()
