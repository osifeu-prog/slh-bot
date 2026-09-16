from core.profile_manager import get_user


def _is_placeholder_name(name, uid):
    value = str(name or "").strip()
    return not value or value == f"User{uid}"


def _telegram_display_name(telegram_user):
    if not telegram_user:
        return None

    first = str(getattr(telegram_user, "first_name", "") or "").strip()
    last = str(getattr(telegram_user, "last_name", "") or "").strip()
    username = str(getattr(telegram_user, "username", "") or "").strip()

    name = " ".join(part for part in (first, last) if part)
    return name or (f"@{username}" if username else None)


def get_display_name(uid, telegram_user=None):
    """Resolve the human-readable SLH identity.

    Priority:
    1. Explicit human name captured during /join
    2. Telegram first_name + last_name
    3. Telegram username
    4. Stored non-placeholder name
    5. User fallback

    ``profile_manager`` historically creates ``User<telegram_id>`` as a
    placeholder. That placeholder must never hide the real Telegram identity.
    """
    uid = str(uid)

    try:
        user = get_user(uid) or {}
        profile = user.get("profile", {}) or {}

        for candidate in (profile.get("name"), user.get("name")):
            if candidate and not _is_placeholder_name(candidate, uid):
                return str(candidate).strip()
    except Exception:
        pass

    telegram_name = _telegram_display_name(telegram_user)
    if telegram_name:
        return telegram_name

    try:
        user = get_user(uid) or {}
        for candidate in (user.get("telegram_name"), user.get("display_name"), user.get("name")):
            if candidate and not _is_placeholder_name(candidate, uid):
                return str(candidate).strip()
    except Exception:
        pass

    return "User"
