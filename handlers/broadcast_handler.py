import time

import state_manager
from core.identity import OWNER_TELEGRAM_ID


BROADCAST_RATE_PER_SECOND = 25
BROADCAST_MIN_INTERVAL = 1.0 / BROADCAST_RATE_PER_SECOND
BROADCAST_MAX_RETRY_AFTER = 60.0


def _retry_after_seconds(exc):
    """Return Telegram's retry_after value when the exception exposes it."""
    value = getattr(exc, "retry_after", None)
    if value is not None:
        try:
            return max(0.0, min(float(value), BROADCAST_MAX_RETRY_AFTER))
        except (TypeError, ValueError):
            pass

    payload = getattr(exc, "result_json", None)
    if isinstance(payload, dict):
        parameters = payload.get("parameters")
        if isinstance(parameters, dict):
            value = parameters.get("retry_after")
            if value is not None:
                try:
                    return max(0.0, min(float(value), BROADCAST_MAX_RETRY_AFTER))
                except (TypeError, ValueError):
                    pass

    return None


def _send_one(bot, uid, message_text, next_allowed_at):
    """Send one message while enforcing the global broadcast pacing."""
    delay = next_allowed_at - time.monotonic()
    if delay > 0:
        time.sleep(delay)

    attempts = 0
    while True:
        try:
            bot.send_message(uid, message_text)
            return True, time.monotonic() + BROADCAST_MIN_INTERVAL

        except Exception as exc:
            retry_after = _retry_after_seconds(exc)
            if retry_after is None or attempts >= 1:
                return False, time.monotonic()

            attempts += 1
            time.sleep(retry_after)


def register(bot):
    @bot.message_handler(commands=["broadcast"])
    def broadcast_cmd(m):
        if int(m.from_user.id) != int(OWNER_TELEGRAM_ID):
            bot.reply_to(m, "⛔ OWNER only")
            return

        parts = (m.text or "").split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(m, "Usage: /broadcast <text>")
            return

        message_text = parts[1].strip()

        try:
            db = state_manager.load_db()
        except Exception as e:
            bot.reply_to(m, f"DB error: {type(e).__name__}")
            return

        users = db.get("users", {})
        if not isinstance(users, dict):
            bot.reply_to(m, "DB error: users registry is invalid")
            return

        sent = 0
        failed = 0
        next_allowed_at = time.monotonic()

        for uid in users.keys():
            ok, next_allowed_at = _send_one(
                bot,
                uid,
                message_text,
                next_allowed_at,
            )
            if ok:
                sent += 1
            else:
                failed += 1

        bot.reply_to(
            m,
            f"✅ Broadcast sent to {sent} users.\n"
            f"Failed: {failed}"
        )
