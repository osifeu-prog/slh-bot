"""Canonical read-only economic projection across SLH ledger sources.

This module does not migrate, rewrite, or mutate any existing financial state.
It normalizes the legacy/user ledger, verified revenue ledger, and isolated
agent ledger into one read-model schema for Control Plane consumers.
"""

from __future__ import annotations

from copy import deepcopy

import state_manager
from core.agent_economy import AgentEconomyService


_AGENT_SERVICE = AgentEconomyService()


_SENSITIVE_KEYS = {
    "token",
    "access_token",
    "api_key",
    "secret",
    "password",
    "authorization",
    "database_url",
    "bot_token",
    "private_key",
}


def _safe_meta(value):
    if isinstance(value, dict):
        return {
            str(k): _safe_meta(v)
            for k, v in value.items()
            if str(k).lower() not in _SENSITIVE_KEYS
        }
    if isinstance(value, list):
        return [_safe_meta(v) for v in value]
    return deepcopy(value)


def _stable_ref(prefix: str, *parts) -> str:
    return prefix + ":" + ":".join(str(part or "") for part in parts)


def normalize_user_event(row: dict) -> dict:
    meta = dict(row.get("meta") or {})
    uid = str(row.get("uid") or "")
    reason = str(row.get("reason") or "")
    timestamp = str(row.get("time") or "")
    operation_ref = str(meta.get("idempotency_key") or "").strip() or _stable_ref(
        "user", uid, timestamp, reason, row.get("amount")
    )
    return {
        "domain": "user",
        "timestamp": timestamp,
        "account_id": uid,
        "counterparty_id": None,