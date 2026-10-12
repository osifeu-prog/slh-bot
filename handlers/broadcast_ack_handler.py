"""Deterministic ACK handler for broadcast messages.

Handles the "ack_seen" callback button without involving any LLM.
Logs each ACK with timestamp so the operator can see who responded.
"""
from __future__ import annotations

from datetime import datetime, timezone

import state_manager


ACK_CALLBACK = "ack_seen"


def _record_ack(uid: str, username: str, first_name: str) -> dict:
    def mutate(db):
        acks = db.setdefault("broadcast_acks", {})
        prev = acks.get(uid, {})
        acks[uid] = {
            "count": int(prev.get("count", 0)) + 1,
            "first_at": prev.get("first_at") or datetime.now(timezone.utc).isoformat(),
            "last_at": datetime.now(timezone.utc).isoformat(),
            "username": username or "",
            "first_name": first_name or "",
        }
        return {"ok": True, "total_acks": len(acks)}
    return state_manager.atomic_update(mutate)


def register(bot):
    @bot.callback_query_handler(func=lambda call: call.data == ACK_CALLBACK)
    def handle_ack(call):
        try:
            u = call.from_user
            uid = str(u.id)
            result = _record_ack(uid, u.username or "", u.first_name or "")
            total = result.get("total_acks", 0)

            bot.answer_callback_query(
                call.id,
                f"✅ תודה! נרשמת ({total} סה\"כ)"
            )
            bot.send_message(
                call.message.chat.id,
                "✅ ראיתי אותך.\n\n"
                "🚀 פתח את ה-Mini App:\n"
                "https://slh-cloud-bot-production.up.railway.app/mini-app-v4"
            )
        except Exception as e:
            try:
                bot.answer_callback_query(call.id, "⚠️ שגיאה זמנית")
            except Exception:
                pass
            print(f"ACK_HANDLER_ERROR: {type(e).name}: {e}")

    print("✅ broadcast_ack handler registered")
