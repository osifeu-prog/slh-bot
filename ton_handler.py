import os
import state_manager

# TON deposits are enabled only through the verified binding flow in
# handlers/ton_address_handler.py and core.ton_deposit_service.
DEFAULT_RATE = 109
TON_RATE_MIN = 100
TON_RATE_MAX = 110


def register_ton_handlers(bot):
    from core.ton_deposit_service import deposits_are_open

    def get_ton_settings():
        db = state_manager.load_db()
        return db.get(
            "ton_settings",
            {
                "credits_per_ton": DEFAULT_RATE,
                "rate": DEFAULT_RATE,
                "testnet": False,
            },
        )

    @bot.message_handler(commands=["ton"])
    def ton_info(m):
        settings = get_ton_settings()
        status = "OPEN" if deposits_are_open() else "CLOSED"
        rate = (
            settings.get("credits_per_ton")
            or settings.get("rate")
            or DEFAULT_RATE
        )
        bot.send_message(
            m.chat.id,
            "💎 TON deposits status: " + status + "\n"
            f"Configured rate: 1 TON = {rate:g} Credits.\n"
            "Use /ton_address for the treasury address and your personal memo."
        )

    @bot.message_handler(commands=["ton_rate"])
    def ton_rate(m):
        from admin_utils import is_admin

        if not is_admin(m):
            return
        parts = m.text.split()
        settings = get_ton_settings()
        current = (
            settings.get("credits_per_ton")
            or settings.get("rate")
            or DEFAULT_RATE
        )
        if len(parts) < 2:
            bot.send_message(
                m.chat.id,
                f"Current rate: 1 TON = {current:g} Credits.",
            )
            return
        try:
            new_rate = float(parts[1])
            if not TON_RATE_MIN <= new_rate <= TON_RATE_MAX:
                raise ValueError
            settings["credits_per_ton"] = new_rate
            settings["rate"] = new_rate
            db = state_manager.load_db()
            db["ton_settings"] = settings
            state_manager.save_db(db)
            bot.send_message(
                m.chat.id,
                f"✅ TON rate updated: 1 TON = {new_rate:g} Credits.",
            )
        except Exception:
            bot.send_message(
                m.chat.id,
                f"Invalid rate. Allowed TON rate: {TON_RATE_MIN:g}-{TON_RATE_MAX:g} Credits per TON.",
            )

    @bot.message_handler(commands=["ton_set_wallet"])
    def ton_set_wallet(m):
        from admin_utils import is_admin

        if not is_admin(m):
            return
        bot.send_message(
            m.chat.id,
            "⛔ TON payout/claim wallet configuration is locked. Use the configured treasury only."
        )


def register(bot):
    return register_ton_handlers(bot)
