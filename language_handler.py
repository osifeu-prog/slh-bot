import state_manager

LANGUAGES = {
    "he": {
        "welcome": "ברוכים הבאים!",
        "balance": "יתרתך: {balance} קרדיטים",
        "buy_prompt": "בחר מוצר:",
        "purchase_success": "✅ רכשת {item} ב-{price} קרדיטים. נותרו: {balance} קרדיטים",
        "help": "שלח /help לעזרה."
    },
    "en": {
        "welcome": "Welcome!",
        "balance": "Your balance: {balance} credits",
        "buy_prompt": "Choose an item:",
        "purchase_success": "✅ Purchased {item} for {price} credits. Remaining: {balance} credits",
        "help": "Type /help for assistance."
    }
}

def register_language(bot):
    @bot.message_handler(commands=['language'])
    def set_language(m):
        parts = m.text.split()
        if len(parts) < 2:
            bot.reply_to(m, "Usage: /language he|en")
            return
        lang = parts[1]
        if lang not in LANGUAGES:
            bot.reply_to(m, "Supported: he, en")
            return
        uid = str(m.from_user.id)
        db = state_manager.load_db()
        db.setdefault("user_settings", {}).setdefault(uid, {})["lang"] = lang
        state_manager.save_db(db)
        bot.reply_to(m, f"Language set to {lang}.")

def get_lang(uid):
    db = state_manager.load_db()
    return db.get("user_settings", {}).get(uid, {}).get("lang", "he")

def translate(key, uid, **kwargs):
    lang = get_lang(uid)
    text = LANGUAGES.get(lang, LANGUAGES["he"]).get(key, key)
    return text.format(**kwargs)
