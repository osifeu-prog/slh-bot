"""Deterministic, private-chat ACK handler for SLH OS broadcasts."""
from __future__ import annotations

from datetime import datetime, timezone

import state_manager

ACK_CALLBACK = "ack_seen"
MINI_APP_URL = "https://slh-cloud-bot-production.up.railway.app/mini-app-v4"


def _record_ack(uid: str, username: str, first_name: str) -> dict:
    """Record at most one ACK per Telegram user; repeated taps are idempotent."""
    uid = str(uid)

    def mutate(db):
        acks = db.setdefault("broadcast_acks", {})
        if not isinstance(acks, dict):
            raise ValueError("BROADCAST_ACK_STORE_INVALID")

        previous = acks.get(uid)
        if previous is not None:
            if not isinstance(previous, dict):
                raise ValueError("BROADCAST_ACK_RECORD_INVALID")
            return {
                "ok": True,
                "status": "ALREADY_ACKED",
                "total_acks": len(acks),
            }

        now = datetime.now(timezone.utc).isoformat()
        acks[uid] = {
            "count": 1,
            "first_at": now,
            "last_at": now,
            "username": str(username or "")[:128],
            "first_name": str(first_name or "")[:128],
        }
        return {"ok": True, "status": "ACKED", "total_acks": len(acks)}

    return state_manager.atomic_update(mutate)


def register(bot):
    @bot.callback_query_handler(func=lambda call: getattr(call, "data", None) == ACK_CALLBACK)
    def handle_ack(call):
        try:
            user = getattr(call, "from_user", None)
            uid = str(getattr(user, "id", "") or "")
            message = getattr(call, "message", None)
            chat = getattr(message, "chat", None)
            chat_id = getattr(chat, "id", None)
            chat_type = str(getattr(chat, "type", "") or "").lower()

            # ACK callbacks must come from a private bot conversation whose chat
            # belongs to the clicking user. Never record or message a group.
            if not uid.isdigit() or chat_type != "private" or str(chat_id) != uid:
                bot.answer_callback_query(
                    call.id,
                    "הקישור לאישור זמין רק בשיחה הפרטית עם הבוט.",
                    show_alert=True,
                )
                return

            result = _record_ack(
                uid,
                str(getattr(user, "username", "") or ""),
                str(getattr(user, "first_name", "") or ""),
            )
            if result.get("status") == "ALREADY_ACKED":
                bot.answer_callback_query(call.id, "✅ האישור כבר נרשם.")
                return

            total = int(result.get("total_acks") or 0)
            bot.answer_callback_query(call.id, f"✅ תודה! האישור נרשם ({total} סה״כ).")
            bot.send_message(
                int(chat_id),
                "✅ ראיתי אותך.\n\n"
                "🚀 פתח את ה-Mini App:\n"
                f"{MINI_APP_URL}",
            )
        except Exception as exc:
            try:
                bot.answer_callback_query(call.id, "⚠️ שגיאה זמנית. נסה שוב מאוחר יותר.")
            except Exception:
                pass
            print(f"BROADCAST_ACK_HANDLER_ERROR: {type(exc).__name__}")

    print("✅ broadcast_ack handler registered")
