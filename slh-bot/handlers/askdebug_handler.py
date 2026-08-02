from core.ask_debug import debug_ask
import json

def register(bot):
    @bot.message_handler(commands=['askdebug'])
    def askdebug_cmd(message):
        try:
            text = message.text.split(' ', 1)[1]
            result = debug_ask(text)
            bot.reply_to(message, '<pre>' + json.dumps(result, indent=2, ensure_ascii=False) + '</pre>', parse_mode='HTML')
        except:
            bot.reply_to(message, 'Usage: /askdebug <question>')
