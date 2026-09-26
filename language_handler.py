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
    },
    "ar": {
        "welcome": "مرحباً!",
        "balance": "رصيدك: {balance} Credits",
        "buy_prompt": "اختر منتجاً:",
        "purchase_success": "✅ اشتريت {item} مقابل {price} Credits. المتبقي: {balance} Credits",
        "help": "اكتب /help للمساعدة."
    },
    "es": {
        "welcome": "¡Bienvenido!",
        "balance": "Tu saldo: {balance} créditos",
        "buy_prompt": "Elige un producto:",
        "purchase_success": "✅ Compraste {item} por {price} créditos. Saldo restante: {balance}",
        "help": "Escribe /help para obtener ayuda."
    },
    "ru": {
        "welcome": "Добро пожаловать!",
        "balance": "Ваш баланс: {balance} кредитов",
        "buy_prompt": "Выберите продукт:",
        "purchase_success": "✅ Вы купили {item} за {price} кредитов. Остаток: {balance} кредитов",
        "help": "Введите /help для помощи."
    },
    "pt": {
        "welcome": "Bem-vindo!",
        "balance": "Seu saldo: {balance} créditos",
        "buy_prompt": "Escolha um produto:",
        "purchase_success": "✅ Você comprou {item} por {price} créditos. Saldo restante: {balance} créditos",
        "help": "Digite /help para obter ajuda."
    },
}

LANGUAGE_NAMES = {
    "he": "עברית",
    "en": "English",
    "ar": "العربية",
    "es": "Español",
    "ru": "Русский",
    "pt": "Português",
}


def normalize_lang(value):
    raw = str(value or "").strip().lower()
    if not raw:
        return None
    code = raw.split("-", 1)[0]
    return code if code in LANGUAGES else None


def ensure_user_language(uid, language_code=None):
    uid = str(uid)
    db = state_manager.load_db()
    settings = db.setdefault("user_settings", {}).setdefault(uid, {})
    existing = normalize_lang(settings.get("lang"))
    if existing:
        return existing

    detected = normalize_lang(language_code)
    if detected:
        settings["lang"] = detected
        state_manager.save_db(db)
        return detected

    settings["lang"] = "he"
    state_manager.save_db(db)
    return "he"


def register_language(bot):
    @bot.message_handler(commands=["language"])
    def set_language(m):
        parts = (m.text or "").split()
        if len(parts) < 2:
            bot.reply_to(
                m,
                "Usage: /language he|en|ar|es|ru|pt\n"
                "Supported: " + " | ".join(f"{k}={v}" for k, v in LANGUAGE_NAMES.items())
            )
            return
        lang = normalize_lang(parts[1])
        if lang is None:
            bot.reply_to(m, "Supported: he | en | ar | es | ru | pt")
            return

        uid = str(m.from_user.id)
        db = state_manager.load_db()
        db.setdefault("user_settings", {}).setdefault(uid, {})["lang"] = lang
        state_manager.save_db(db)
        bot.reply_to(m, f"Language set to {LANGUAGE_NAMES[lang]}.")


def get_lang(uid):
    db = state_manager.load_db()
    configured = normalize_lang(
        db.get("user_settings", {}).get(str(uid), {}).get("lang")
    )
    return configured or "he"


def translate(key, uid, **kwargs):
    lang = get_lang(uid)
    text = LANGUAGES.get(lang, LANGUAGES["he"]).get(key, key)
    return text.format(**kwargs)
