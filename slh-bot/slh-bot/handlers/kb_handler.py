MAP = {'a': 'ש', 'b': 'נ', 'c': 'ב', 'd': '', 'e': 'ק', 'f': 'כ', 'g': 'ע', 'h': 'י', 'i': 'ן', 'j': 'ח', 'k': 'ל', 'l': 'ך', 'm': 'צ', 'n': 'מ', 'o': 'ם', 'p': 'פ', 'q': '/', 'r': 'ר', 's': 'ד', 't': 'א', 'u': 'ו', 'v': 'ה', 'w': "'", 'x': 'ס', 'y': 'ט', 'z': 'ז', ',': 'ת', '.': 'ץ', '/': '.', "'": ','}

def fix_hebrew(text):
    return "".join(MAP.get(c, c) for c in text)

def register(bot):
    @bot.message_handler(commands=['fixkb'])
    def fixkb(m):
        parts = m.text.split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(m, "Usage: /fixkb <text>")
            return
        fixed = fix_hebrew(parts[1])
        bot.reply_to(m, fixed)
