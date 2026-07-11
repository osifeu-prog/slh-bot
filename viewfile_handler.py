import os
from admin_utils import is_admin

MAX_CHARS = 3800

def register(bot):
    @bot.message_handler(commands=['viewfile'])
    def viewfile(m):
        if not is_admin(m):
            bot.reply_to(m, "❌ Admin only")
            return
        parts = m.text.split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(m, "Usage: /viewfile <path>\nExample: /viewfile bot_stable.py")
            return
        path = parts[1].strip()
        full_path = os.path.join(os.getcwd(), path)
        if not os.path.abspath(full_path).startswith(os.getcwd()):
            bot.reply_to(m, "❌ Path outside project directory not allowed")
            return
        if not os.path.exists(full_path):
            bot.reply_to(m, f"❌ File not found: {path}")
            return
        if not os.path.isfile(full_path):
            bot.reply_to(m, f"❌ Not a file: {path}")
            return
        try:
            with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
        except Exception as e:
            bot.reply_to(m, f"❌ Error reading file: {e}")
            return
        total_lines = content.count('\n') + 1
        header = f"📄 {path} ({total_lines} lines, {len(content)} chars)\n\n"
        if len(content) <= MAX_CHARS:
            bot.reply_to(m, header + content)
        else:
            bot.reply_to(m, header + "⚠️ File too long, sending in chunks:")
            chunks = [content[i:i+MAX_CHARS] for i in range(0, len(content), MAX_CHARS)]
            for idx, chunk in enumerate(chunks, 1):
                bot.send_message(m.chat.id, f"[{idx}/{len(chunks)}]\n```\n{chunk}\n```", parse_mode="Markdown")
