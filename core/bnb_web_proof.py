"""One-time browser session for bot-driven BNB wallet ownership proof.

The Telegram bot creates a short-lived session bound to a specific Telegram user
and BSC address. The external browser page may request an injected wallet signature,
but this module never stores private keys or asks for a transaction.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
import os
import secrets

import state_manager
from core.wallet_binding import get_binding, issue_challenge, normalize_address

SESSION_TTL_SECONDS = 600


def _now():
    return datetime.now(timezone.utc)


def _iso(dt):
    return dt.isoformat()


def _parse_iso(value):
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _base_url() -> str:
    explicit = (os.getenv("SLH_PUBLIC_BASE_URL") or "").strip().rstrip("/")
    if explicit:
        return explicit
    domain = (os.getenv("RAILWAY_PUBLIC_DOMAIN") or "").strip()
    if domain:
        return domain if domain.startswith("http") else f"https://{domain}"
    return "https://slh-cloud-bot-production.up.railway.app"


def issue_session(uid: str, address: str) -> dict:
    uid = str(uid)
    address = normalize_address(address)

    challenge = issue_challenge(uid, address)
    token = secrets.token_urlsafe(32)
    expires_at = _now() + timedelta(seconds=SESSION_TTL_SECONDS)

    def mutate(db):
        sessions = db.setdefault("bnb_web_proof_sessions", {})
        sessions[token] = {
            "uid": uid,
            "chain": "bsc",
            "address": address,
            "created_at": _iso(_now()),
            "expires_at": _iso(expires_at),
            "consumed": False,
        }

    state_manager.atomic_update(mutate)
    return {
        "session": token,
        "url": f"{_base_url()}/wallet/bnb-sign?session={token}",
        "address": address,
        "message": challenge["message"],
        "expires_at": _iso(expires_at),
    }


def get_session(token: str) -> dict:
    token = str(token or "").strip()
    if not token:
        raise ValueError("BSC_WEB_SESSION_INVALID")

    db = state_manager.load_db()
    session = db.get("bnb_web_proof_sessions", {}).get(token)
    if not isinstance(session, dict) or session.get("consumed"):
        raise ValueError("BSC_WEB_SESSION_NOT_FOUND")
    if _now() >= _parse_iso(session["expires_at"]):
        raise ValueError("BSC_WEB_SESSION_EXPIRED")

    uid = str(session["uid"])
    address = normalize_address(session["address"])
    challenge = db.get("wallet_challenges", {}).get(f"bsc:{uid}")
    if not isinstance(challenge, dict) or challenge.get("consumed"):
        raise ValueError("BSC_CHALLENGE_NOT_FOUND")
    if str(challenge.get("address", "")).lower() != address.lower():
        raise ValueError("BSC_CHALLENGE_ADDRESS_MISMATCH")

    return {
        "uid": uid,
        "chain": "bsc",
        "address": address,
        "message": challenge["message"],
        "expires_at": session["expires_at"],
    }


def consume_session(token: str) -> dict:
    token = str(token or "").strip()

    def mutate(db):
        session = db.get("bnb_web_proof_sessions", {}).get(token)
        if not isinstance(session, dict) or session.get("consumed"):
            raise ValueError("BSC_WEB_SESSION_NOT_FOUND")
        if _now() >= _parse_iso(session["expires_at"]):
            raise ValueError("BSC_WEB_SESSION_EXPIRED")
        session["consumed"] = True
        session["consumed_at"] = _iso(_now())
        return dict(session)

    return state_manager.atomic_update(mutate)


def verify_session(token: str, signature: str) -> dict:
    session = get_session(token)

    from core.wallet_binding import verify_signature
    binding = verify_signature(
        session["uid"],
        session["address"],
        signature,
    )
    try:
        consume_session(token)
    except ValueError:
        # The underlying one-time wallet challenge has already made the proof
        # single-use. Surface the successful binding rather than failing a
        # harmless finalization race.
        pass

    return binding
