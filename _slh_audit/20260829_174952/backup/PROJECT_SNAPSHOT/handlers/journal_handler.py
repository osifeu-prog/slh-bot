import json, os
from datetime import datetime

JOURNAL_DIR = '/app/state/journals'

def register(bot):
    os.makedirs(JOURNAL_DIR, exist_ok=True)
    
    @bot.message_handler(commands=['journal'])
    def journal_write(msg):
        uid = str(msg.from_user.id)
        text = msg.text.replace('/journal', '', 1).strip()
        if not text:
            bot.reply_to(msg, 'Usage: /journal <your entry>')
            return
        entry = {'timestamp': datetime.utcnow().isoformat(), 'text': text}
        path = os.path.join(JOURNAL_DIR, f'{uid}.jsonl')
        with open(path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        bot.reply_to(msg, '📓 Entry saved!')

    @bot.message_handler(commands=['journal_read'])
    def journal_read(msg):
        uid = str(msg.from_user.id)
        path = os.path.join(JOURNAL_DIR, f'{uid}.jsonl')
        if not os.path.exists(path):
            bot.reply_to(msg, '📓 No entries yet.')
            return
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()[-5:]
        if not lines:
            bot.reply_to(msg, '📓 No entries yet.')
            return
        output = '📓 Your last entries:\n\n'
        for line in lines:
            e = json.loads(line)
            output += f"🕒 {e['timestamp'][:16]}\n{e['text']}\n\n"
        bot.reply_to(msg, output)
