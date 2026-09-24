import state_manager

# TON claim is intentionally disabled until deposits are bound to the
# requesting Telegram account by a verifiable ownership protocol.
DEFAULT_RATE = 100


def register_ton_handlers(bot):
    def get_ton_settings():
        db = state_manager.load_db()
        return db.setdefault("ton_settings", {"rate": DEFAULT_RATE, "testnet": False})

    @bot.message_handler(commands=['ton'])
    def ton_info(m):
        settings = get_ton_settings()
        bot.send_message(
            m.chat.id,
            "💎 TON deposits are temporarily paused.\n"
            "Automated crediting will return after verified user-binding is implemented.\n"
            f"Current configured rate: 1 TON = {settings.get('rate', DEFAULT_RATE)} Credits."
        )

    @bot.message_handler(commands=['ton'])
    def ton_info(m):
        settings = get_ton_settings()
        open_flag = __import__("os").getenv("TON_DEPOSITS_OPEN", "0").strip() == "1"
        status = "OPEN" if open_flag else "CLOSED"
        bot.send_message(
            m.chat.id,
            "💎 TON deposits status: " + status + "\n"
            f"Configured rate: 1 TON = {settings.get('credits_per_ton', settings.get('rate', DEFAULT_RATE))} Credits.\n"
            "Use /ton_address for the treasury address and your personal memo."
        )

    @bot.message_handler(commands=['ton_rate'])
    def ton_rate(m):
        from admin_utils import is_admin
        if not is_admin(m):
            return
        parts = m.text.split()
        settings = get_ton_settings()
        if len(parts) < 2:
            bot.send_message(m.chat.id, f"Current rate: 1 TON = {settings.get('rate', DEFAULT_RATE)} Credits.")
            return
        try:
            new_rate = float(parts[1])
            if new_rate <= 0:
                raise ValueError
            settings["rate"] = new_rate
            db = state_manager.load_db()
            db["ton_settings"] = settings
            state_manager.save_db(db)
            bot.send_message(m.chat.id, f"✅ TON rate updated: 1 TON = {new_rate} Credits.")
        except Exception:
            bot.send_message(m.chat.id, "Invalid rate.")

    @bot.message_handler(commands=['ton_set_wallet'])
    def ton_set_wallet(m):
        from admin_utils import is_admin
        if not is_admin(m):
            return
        bot.send_message(
            m.chat.id,
            "⛔ TON payout/claim wallet configuration is temporarily locked while claim binding is redesigned."
        )


def register(bot):
    return register_ton_handlers(bot)
