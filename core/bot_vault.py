"""Encrypted owner-managed Telegram bot token vault.

Tokens are verified with Telegram getMe() before storage and encrypted with
Fernet using SLH_VAULT_KEY. Plain tokens are never returned by public APIs or
written to the audit log.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import requests

import state_manager

API = "https://api.telegram.org/bot{token}/{method}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fernet():
    key = os.getenv("SLH_VAULT_KEY", "").strip()
    if not key:
        raise ValueError("VAULT_KEY_MISSING")
    from cryptography.fernet import Fernet
    return Fernet(key.encode())


def _tail(token: str) -> str:
    return "…" + str(token)[-4:]


def _tg(token: str, method: str, timeout: int = 15) -> dict:
    try:
        response = requests.get(API.format(token=token, method=method), timeout=timeout)
        return response.json()
    except Exception as exc:
        return {"ok": False, "description": type(exc).__name__}


def _verify(token: str) -> dict:
    token = str(token or "").strip()
    if ":" not in token or not token.split(":", 1)[0].isdigit():
        raise ValueError("INVALID_TOKEN_FORMAT")
    me = _tg(token, "getMe")
    if not me.get("ok"):
        raise ValueError("TOKEN_REJECTED_BY_TELEGRAM")
    result = me.get("result") or {}
    bot_id = str(result.get("id") or "")
    username = str(result.get("username") or "").lstrip("@")
    if not bot_id or not username:
        raise ValueError("TOKEN_MISSING_BOT_ID_OR_USERNAME")
    return {"bot_id": bot_id, "username": username, "name": result.get("first_name", "")}


def _audit(db: dict, actor: Any, action: str, username: str, token: str | None = None, note: str = "") -> None:
    db.setdefault("bot_vault_audit", []).append({
        "at": _now(),
        "actor": str(actor),
        "action": action,
        "bot": username,
        "token_tail": _tail(token) if token else "",
        "note": str(note)[:200],
    })


def add_bot(token: str, actor: Any, module: str = "home", role: str = "redirect") -> dict:
    token = str(token or "").strip()
    info = _verify(token)
    encrypted = _fernet().encrypt(token.encode()).decode()

    def mutate(db: dict):
        vault = db.setdefault("bot_vault", {})
        existed = info["username"] in vault
        entry = vault.get(info["username"], {})
        entry.update({
            "bot_id": info["bot_id"],
            "username": info["username"],
            "name": info["name"],
            "token_enc": encrypted,
            "token_tail": _tail(token),
            "module": str(module or "home")[:40],
            "role": str(role or "redirect")[:40],
            "added_at": entry.get("added_at") or _now(),
            "updated_at": _now(),
            "exposures": entry.get("exposures", []),
        })
        vault[info["username"]] = entry
        _audit(db, actor, "update" if existed else "add", info["username"], token)
        return {k: v for k, v in entry.items() if k != "token_enc"}

    return state_manager.atomic_update(mutate)


def remove_bot(username: str, actor: Any) -> bool:
    username = str(username or "").strip().lstrip("@")

    def mutate(db: dict):
        vault = db.setdefault("bot_vault", {})
        if username not in vault:
            raise ValueError("BOT_NOT_IN_VAULT")
        tail = vault[username].get("token_tail", "")
        del vault[username]
        _audit(db, actor, "remove", username, note=f"token {tail} deleted from vault")
        return True

    return state_manager.atomic_update(mutate)


def rotate_bot(username: str, new_token: str, actor: Any) -> dict:
    username = str(username or "").strip().lstrip("@")
    new_token = str(new_token or "").strip()
    info = _verify(new_token)
    db = state_manager.load_db()
    current = (db.get("bot_vault") or {}).get(username)
    if not current:
        raise ValueError("BOT_NOT_IN_VAULT")
    if str(current.get("bot_id")) != info["bot_id"] or info["username"] != username:
        raise ValueError("TOKEN_BELONGS_TO_ANOTHER_BOT")

    encrypted = _fernet().encrypt(new_token.encode()).decode()

    def mutate(db2: dict):
        entry = db2["bot_vault"][username]
        old_tail = entry.get("token_tail", "")
        entry.update({
            "token_enc": encrypted,
            "token_tail": _tail(new_token),
            "rotated_at": _now(),
            "updated_at": _now(),
        })
        for exposure in entry.get("exposures", []):
            exposure.setdefault("resolved_at", _now())
        _audit(db2, actor, "rotate", username, new_token, note=f"replaced {old_tail}")
        return {k: v for k, v in entry.items() if k != "token_enc"}

    return state_manager.atomic_update(mutate)


def mark_exposed(username: str, source: str, actor: Any, note: str = "") -> dict:
    username = str(username or "").strip().lstrip("@")

    def mutate(db: dict):
        entry = (db.get("bot_vault") or {}).get(username)
        if not entry:
            raise ValueError("BOT_NOT_IN_VAULT")
        rec = {
            "source": str(source or "unknown")[:80],
            "at": _now(),
            "note": str(note or "")[:200],
            "recommendation": "rotate when convenient",
        }
        entry.setdefault("exposures", []).append(rec)
        _audit(db, actor, "exposure", username, note=f"{source}: {note}")
        return rec

    return state_manager.atomic_update(mutate)


def get_token(username: str) -> str:
    username = str(username or "").strip().lstrip("@")
    entry = (state_manager.load_db().get("bot_vault") or {}).get(username)
    if not entry:
        raise ValueError("BOT_NOT_IN_VAULT")
    token_enc = str(entry.get("token_enc") or "")
    if not token_enc:
        raise ValueError("VAULT_ENTRY_CORRUPT")
    return _fernet().decrypt(token_enc.encode()).decode()

def get_token_by_identity(username: str) -> str:
    """Resolve a vault token by case-insensitive Telegram username."""
    wanted = str(username or "").strip().lstrip("@").casefold()
    if not wanted:
        raise ValueError("BOT_NOT_IN_VAULT")
    vault = state_manager.load_db().get("bot_vault") or {}
    for key, entry in vault.items():
        stored = str((entry or {}).get("username") or key).strip().lstrip("@").casefold()
        if stored == wanted:
            token_enc = str((entry or {}).get("token_enc") or "")
            if not token_enc:
                raise ValueError("VAULT_ENTRY_CORRUPT")
            return _fernet().decrypt(token_enc.encode()).decode()
    raise ValueError("BOT_NOT_IN_VAULT")


def health(username: str) -> dict:
    token = get_token(username)
    me = _tg(token, "getMe")
    webhook = _tg(token, "getWebhookInfo") if me.get("ok") else {}
    result = webhook.get("result") or {}
    return {
        "bot": str(username).lstrip("@"),
        "alive": bool(me.get("ok")),
        "webhook": bool(result.get("url")),
        "pending": int(result.get("pending_update_count") or 0),
        "last_error": str(result.get("last_error_message") or ""),
    }


def list_bots() -> list[dict]:
    vault = state_manager.load_db().get("bot_vault") or {}
    out = []
    for username, entry in sorted(vault.items()):
        open_exposures = [x for x in entry.get("exposures", []) if not x.get("resolved_at")]
        out.append({
            "username": username,
            "module": entry.get("module", "home"),
            "role": entry.get("role", "redirect"),
            "token_tail": entry.get("token_tail", ""),
            "rotated_at": entry.get("rotated_at", ""),
            "open_exposures": len(open_exposures),
        })
    return out
