# DEPRECATED
# Canonical /ask handler:
# handlers.advanced_ask_handler.register_ask_handler(bot)
#
# Runtime loading is owned by handlers.loader.py.
# This module intentionally registers NO Telegram handlers.

def register_ask_handler(bot):
    print("ℹ️ root advanced_ask_handler deprecated - canonical handler is handlers.advanced_ask_handler")
    return None
