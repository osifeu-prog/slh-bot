import json
import time

from core.identity import OWNER_TELEGRAM_ID

MAX_BROADCAST_CHARS = 4000
BROADCAST_INTERVAL_SECONDS = 0.08
MAX_RETRIES = 2


def _retry_after(exc) -> float:
    payload = getattr(exc, "result_json", None)
    if isinstance(payload, dict):
        parameters = payload.get("parameters") or {}
        try:
            return max(1.0, min(60.0, float(parameters.get("retry_after", 1))))
        except (TypeError, ValueError):
            pass
    return 1.0


def perform_broadcast(bot, user_ids, message_text):
    sent = 0
    failed = 0

    for uid in user_ids:
        for attempt in range(MAX_RETRIES + 1):
            try:
                bot.send_message(uid, message_text)
                sent += 1
                time.sleep(BROADCAST_INTERVAL_SECONDS)
                break
            except Exception as exc:
                if getattr(exc, "error_code", None) == 429 and attempt < MAX_RETRIES:
                    time.sleep(_retry_after(exc))
                    continue
                failed += 1
                break

    return {"sent": sent, "failed": failed}


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
        if not message_text:
            bot.reply_to(m, "Usage: /broadcast <text>")
            return
        if len(message_text) > MAX_BROADCAST_CHARS:
            bot.reply_to(
                m,
                f"❌ Broadcast too long. Maximum {MAX_BROADCAST_CHARS} characters.",
            )
            return

        try:
            with open("state/db.json", encoding="utf-8") as handle:
                db = json.load(handle)
        except Exception as exc:
            bot.reply_to(m, f"DB error: {type(exc).__name__}")
            return

        users = db.get("users", {})
        if not isinstance(users, dict):
            bot.reply_to(m, "DB error: invalid users state")
            return

        result = perform_broadcast(bot, users.keys(), message_text)

        bot.reply_to(
            m,
            f"✅ Broadcast sent to {result['sent']} users.\n"
            f"Failed: {result['failed']}",
        )
