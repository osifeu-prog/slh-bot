"""TON payment handlers.

Incoming TON crediting is intentionally disabled until the claimant can be
cryptographically/verifiably bound to the source deposit address.
"""


def register_ton_handlers(bot):
    @bot.message_handler(commands=["ton"])
    def ton_info(m):
        bot.send_message(
            m.chat.id,
            "⛔ TON deposits are temporarily paused.\n"
            "Automated crediting will return after verified user-binding is implemented.",
        )

    @bot.message_handler(commands=["ton_check"])
    def ton_check(m):
        bot.send_message(
            m.chat.id,
            "⛔ /ton_check מושבת זמנית.\n"
            "אימות TX לבדו אינו מוכיח שההפקדה שייכת לחשבון Telegram המבקש.\n"
            "המסלול יופעל מחדש רק לאחר הוספת user-binding מאומת.",
        )

    @bot.message_handler(commands=["ton_rate"])
    def ton_rate(m):
        from admin_utils import is_admin
        if not is_admin(m):
            return
        bot.send_message(m.chat.id, "⛔ TON deposits are paused; rate changes are disabled.")

    @bot.message_handler(commands=["ton_set_wallet"])
    def ton_set_wallet(m):
        from admin_utils import is_admin
        if not is_admin(m):
            return
        bot.send_message(m.chat.id, "⛔ TON wallet changes are disabled while deposits are paused.")

    print("✅ ton_handler loaded (TON claims disabled pending user-binding)")


def register(bot):
    return register_ton_handlers(bot)
