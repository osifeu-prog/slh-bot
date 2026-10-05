"""Short-lived wallet handoff sessions for external wallet browsers.

A Telegram-authenticated Mini App can create a one-time handoff code. The code is
exchanged for an HttpOnly cookie before entering the dedicated wallet-connect
page. The raw code is never persisted; only its SHA-256 digest is stored.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import secrets
from typing import Any

import state_manager

KEY = "wallet_handoffs"
TTL_SECONDS = 900


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat()


def _hash(token: str) -> str:
    return hashlib.sha256(str(token).encode("utf-8")).hexdigest()


def create_handoff(uid: Any) -> dict[str, Any]:
    target = str(uid).strip()
    if not target.isdigit() or int(target) <= 0:
        raise ValueError("INVALID_USER_ID")

    token = secrets.token_urlsafe(32)
    now = _now()
    expires = now + timedelta(seconds=TTL_SECONDS)
    digest = _hash(token)

    def mutate(db: dict) -> None:
        rows = db.setdefault(KEY, {})
        for key, row in list(rows.items()):
            if not isinstance(row, dict):
                rows.pop(key, None)
                continue
            try:
                row_expiry = datetime.fromisoformat(
                    str(row.get("expires_at")).replace("Z", "+00:00")
                )
            except (TypeError, ValueError):
                rows.pop(key, None)
                continue
            if row_expiry <= now:
                rows.pop(key, None)

        rows[digest] = {
            "uid": target,
            "created_at": _iso(now),
            "expires_at": _iso(expires),
            "consumed_at": None,
            "scope": "wallet",
        }

    state_manager.atomic_update(mutate)
    return {"token": token, "expires_at": _iso(expires), "ttl_seconds": TTL_SECONDS}


def consume_handoff(token: Any) -> str:
    raw = str(token or "").strip()
    if not raw or len(raw) < 20 or len(raw) > 256:
        raise ValueError("INVALID_WALLET_HANDOFF")

    digest = _hash(raw)
    now = _now()

    def mutate(db: dict) -> str:
        rows = db.get(KEY, {}) if isinstance(db, dict) else {}
        row = rows.get(digest) if isinstance(rows, dict) else None
        if not isinstance(row, dict):
            raise ValueError("WALLET_HANDOFF_NOT_FOUND")

        try:
            expires = datetime.fromisoformat(
                str(row.get("expires_at")).replace("Z", "+00:00")
            )
        except (TypeError, ValueError):
            raise ValueError("WALLET_HANDOFF_INVALID")

        if now >= expires:
            rows.pop(digest, None)
            raise ValueError("WALLET_HANDOFF_EXPIRED")

        uid = str(row.get("uid") or "").strip()
        if not uid.isdigit() or int(uid) <= 0:
            raise ValueError("WALLET_HANDOFF_INVALID")

        if row.get("consumed_at"):
            raise ValueError("WALLET_HANDOFF_ALREADY_CONSUMED")
        row["consumed_at"] = _iso(now)
        rows[digest] = row
        return uid

    return state_manager.atomic_update(mutate)


def validate_session(token: Any) -> str | None:
    raw = str(token or "").strip()
    if not raw or len(raw) < 20 or len(raw) > 256:
        return None

    digest = _hash(raw)
    now = _now()
    db = state_manager.load_db()
    rows = db.get(KEY, {}) if isinstance(db, dict) else {}
    row = rows.get(digest) if isinstance(rows, dict) else None
    if not isinstance(row, dict):
        return None

    try:
        expires = datetime.fromisoformat(
            str(row.get("expires_at")).replace("Z", "+00:00")
        )
    except (TypeError, ValueError):
        return None
    if now >= expires:
        return None

    uid = str(row.get("uid") or "").strip()
    return uid if uid.isdigit() and int(uid) > 0 else None
