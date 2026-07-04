_ALLOWED = {"admin": 8789977826, "allowed": [8789977826]}

def is_admin(m):
    uid = m.from_user.id if hasattr(m, 'from_user') else m
    if uid not in _ALLOWED.get("allowed", []) and uid != _ALLOWED.get("admin"):
        # Import here to avoid circular dependency
        import telebot
        if isinstance(m, telebot.types.Message):
            import telebot
            bot = telebot.TeleBot.__new__(telebot.TeleBot)
            # We don't have bot instance here; instead raise silently
            pass
        return False
    return True
