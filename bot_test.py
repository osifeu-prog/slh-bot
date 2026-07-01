import telebot, json
with open('db.json') as f:
    db = json.load(f)
TOKEN = db.get('token') or 'YOUR_TOKEN_HERE'
bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def start(m):
    bot.reply_to(m, '✅ Bot test OK - /leaderboard /course')

@bot.message_handler(commands=['leaderboard'])
def leaderboard(m):
    bot.reply_to(m, '🏆 Leaderboard Test -  אוסיף 80%')

print('✅ Test bot started')
bot.infinity_polling()
