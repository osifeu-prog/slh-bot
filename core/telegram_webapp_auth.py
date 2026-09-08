"""Server-side authentication for Telegram Mini App initData."""

import hashlib
import hmac
import json
import os
import time
from urllib.parse import parse_qsl


DEFAULT_MAX_AGE = 3600


def _bot_token():
    token = str(os.getenv("BOT_TOKEN", "")).strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN_MISSING")
    return token


def validate_init_data(init_data, max_age=DEFAULT_MAX_AGE, now=None):
    """Validate Telegram WebApp initData and return the authenticated user.

    The Telegram WebApp signature is checked server-side. The returned UID must
    never be taken from initDataUnsafe on the client.
    """
    if not isinstance(init_data, str) or not init_data.strip():
        raise ValueError("TELEGRAM_INIT_DATA_MISSING")

    pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=True)
    data = dict(pairs)
    received_hash = data.pop("hash", "")
    if not received_hash:
        raise ValueError("TELEGRAM_INIT_DATA_HASH_MISSING")

    check_string = "\n".join(
        f"{key}={value}" for key, value in sorted(data.items())
    )
    secret_key = hmac.new(
        b"WebAppData", _bot_token().encode("utf-8"), hashlib.sha256
    ).digest()
    expected_hash = hmac.new(
        secret_key, check_string.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(received_hash.lower(), expected_hash):
        raise ValueError("TELEGRAM_INIT_DATA_INVALID")

    try:
        auth_date = int(data.get("auth_date", "0"))
    except (TypeError, ValueError):
        raise ValueError("TELEGRAM_INIT_DATA_AUTH_DATE_INVALID")

    current_time = int(time.time() if now is None else now)
    if auth_date <= 0 or auth_date > current_time + 60:
        raise ValueError("TELEGRAM_INIT_DATA_AUTH_DATE_INVALID")
    if current_time - auth_date > int(max_age):
        raise ValueError("TELEGRAM_INIT_DATA_EXPIRED")

    try:
        user = json.loads(data.get("user", "{}"))
    except json.JSONDecodeError:
        raise ValueError("TELEGRAM_INIT_DATA_USER_INVALID")

    uid = user.get("id")
    if uid is None:
        raise ValueError("TELEGRAM_INIT_DATA_USER_MISSING")

    return {"uid": str(uid), "user": user, "auth_date": auth_date}
