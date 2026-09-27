"""Small persistent per-user conversation memory for the SLH AI chat.

The memory is intentionally bounded and stored inside the canonical state/db.json.
It is conversational context only: it never grants permissions or executes actions.
"""

from __future__ import annotations

import re
import time

import state_manager


MAX_TURNS = 8
MAX_TEXT_CHARS = 1600

_CONTINUE_RE = re.compile(
    r"^(?:כן|כן בבקשה|כן,? ?בבקשה|המשך|תמשיך|תמשיכי|בוא נמשיך|"
    r"יאללה|קדימה|sure|yes|yes please|continue|go on|ok|okay|proceed)"
    r"[.!…\s]*$",
    re.IGNORECASE,
)

_SECRET_RE = re.compile(
    r"(?i)(?:"
    r"\b\d{8,12}:AA[A-Za-z0-9_-]{30,}\b|"
    r"\b(?:sk-|gsk_)[A-Za-z0-9_-]{20,}\b|"
    r"\bAIza[0-9A-Za-z_-]{30,}\b|"
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----"
    r")"
)


def is_continuation(text: str) -> bool:
    value = str(text or "").strip()
    return bool(_CONTINUE_RE.fullmatch(value))


def _safe_text(value: str) -> str:
    text = str(value or "").replace("\x00", "").strip()
    text = _SECRET_RE.sub("[REDACTED]", text)
    if len(text) > MAX_TEXT_CHARS:
        text = text[:MAX_TEXT_CHARS] + "…"
    return text


def record_turn(uid: str, user_text: str, assistant_text: str, intent: str | None = None) -> None:
    uid = str(uid)
    user = _safe_text(user_text)
    assistant = _safe_text(assistant_text)
    if not user or not assistant:
        return

    def mutate(db):
        memory = db.setdefault("memory", {})
        conversations = memory.setdefault("conversations", {})
        state = conversations.setdefault(
            uid,
            {"history": [], "updated_at": 0},
        )
        history = state.setdefault("history", [])
        history.append(
            {
                "ts": time.time(),
                "user": user,
                "assistant": assistant,
                "intent": str(intent or ""),
            }
        )
        del history[:-MAX_TURNS]
        state["updated_at"] = time.time()
        return None

    state_manager.atomic_update(mutate)


def get_history(uid: str, limit: int = MAX_TURNS) -> list[dict]:
    uid = str(uid)
    try:
        db = state_manager.load_db()
        rows = (
            db.get("memory", {})
            .get("conversations", {})
            .get(uid, {})
            .get("history", [])
        )
        if not isinstance(rows, list):
            return []
        cleaned = [row for row in rows if isinstance(row, dict)]
        return cleaned[-max(1, int(limit)):]
    except Exception:
        return []


def last_turn(uid: str) -> dict | None:
    rows = get_history(uid, 1)
    return rows[0] if rows else None


def format_history(uid: str, limit: int = MAX_TURNS) -> str:
    rows = get_history(uid, limit)
    if not rows:
        return "אין היסטוריית שיחה זמינה."

    lines = []
    for row in rows:
        user = str(row.get("user") or "").strip()
        assistant = str(row.get("assistant") or "").strip()
        if user and assistant:
            lines.append(f"משתמש: {user}\nSLH: {assistant}")
    return "\n\n".join(lines) or "אין היסטוריית שיחה זמינה."


def clear_history(uid: str) -> None:
    uid = str(uid)

    def mutate(db):
        conversations = (
            db.setdefault("memory", {})
            .setdefault("conversations", {})
        )
        conversations[uid] = {"history": [], "updated_at": time.time()}
        return None

    state_manager.atomic_update(mutate)
