from core.profile_manager import get_user

def get_display_name(uid, telegram_user=None):
    """
    SLH identity display resolver.
    Priority:
    1. Stored SLH profile name
    2. User name
    3. Telegram first_name
    4. User fallback
    """

    try:
        user = get_user(uid) or {}

        profile = user.get("profile", {})
        name = profile.get("name")

        if name:
            return name

        name = user.get("name")
        if name:
            return name

    except Exception:
        pass

    if telegram_user:
        return getattr(telegram_user, "first_name", None) or "User"

    return "User"
