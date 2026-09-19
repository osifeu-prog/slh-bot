"""Legacy bot_factory compatibility module.

Project listing is owned by handlers.deploy_handler. This module intentionally
registers no duplicate Telegram commands.
"""


def register(bot):
    print("✅ bot_factory loaded (no duplicate project command)")
