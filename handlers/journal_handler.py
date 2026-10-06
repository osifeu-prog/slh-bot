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
        # Normalize: replace literal backslash-n in the entry text to avoid
        # corrupting the jsonl file (each line must be one valid JSON object).
        safe_text = text.replace('\r', ' ').replace('\n', ' ')
        safe_text = safe_text.replace('\\n', ' ')
        entry['text'] = safe_text
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

        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as exc:
            bot.reply_to(msg, f'❌ Read error: {type(exc).__name__}')
            return

        # Defensive: older entries may contain literal "\n" sequences
        # instead of real newlines. Normalize before splitting.
        content = content.replace('\\n', '\n')
        raw_lines = [line.strip() for line in content.split('\n') if line.strip()]
        raw_lines = raw_lines[-5:]

        if not raw_lines:
            bot.reply_to(msg, '📓 No entries yet.')
            return

        output = '📓 Your last entries:\n\n'
        parsed_any = False
        for line in raw_lines:
            try:
                entry = json.loads(line)
            except Exception:
                # Skip corrupt lines silently
                continue
            ts = str(entry.get('timestamp', '?'))[:16]
            text = str(entry.get('text', ''))
            output += f"🕒 {ts}\n{text}\n\n"
            parsed_any = True

        if not parsed_any:
            bot.reply_to(msg, '📓 Journal entries are corrupt.')
            return

        # Telegram message limit is 4096 chars
        if len(output) > 4000:
            output = output[:3997] + '...'

        bot.reply_to(msg, output)