"""Canonical read-only economic projection across SLH ledger sources.

This module does not migrate, rewrite, or mutate any existing financial state.
It normalizes the legacy/user ledger, verified revenue ledger, and isolated
agent ledger into one read-model schema for Control Plane consumers.
"""

from __future__ import annotations

from copy import deepcopy

import state_manager
from slh_mcp.agent_economy import AgentEconomyService


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
        "amount": float(row.get("amount", 0) or 0),
        "currency": "credits",
        "operation_ref": operation_ref,
        "event_type": "ledger",
        "source": "user_ledger",
        "actor": uid,
        "reason": reason,
        "before": row.get("before"),
        "after": row.get("after"),
        "meta": _safe_meta(meta),
    }


def normalize_revenue_event(row: dict) -> dict:
    uid = row.get("uid")
    source = str(row.get("source") or "")
    reference = str(row.get("reference") or "")
    return {
        "domain": "revenue",
        "timestamp": str(row.get("timestamp") or ""),
        "account_id": str(uid) if uid is not None else source,
        "counterparty_id": source,
        "amount": float(row.get("amount", 0) or 0),
        "currency": str(row.get("currency") or "UNKNOWN"),
        "operation_ref": reference or _stable_ref("revenue", source, row.get("timestamp")),
        "event_type": "revenue",
        "source": source,
        "actor": str(uid) if uid is not None else None,
        "reason": "verified_external_revenue",
        "before": None,
        "after": None,
        "meta": _safe_meta(row.get("meta") or {}),
    }


def normalize_agent_event(row: dict) -> dict:
    return {
        "domain": "agent",
        "timestamp": str(row.get("timestamp") or ""),
        "account_id": str(row.get("account") or ""),
        "counterparty_id": (
            str(row.get("counterparty"))
            if row.get("counterparty") is not None
            else None
        ),
        "amount": float(row.get("amount", 0) or 0),
        "currency": "agent_credits",
        "operation_ref": str(row.get("operation_id") or ""),
        "event_type": str(row.get("entry_type") or "agent_ledger"),
        "source": "agent_ledger",
        "actor": str(row.get("actor") or ""),
        "reason": str(row.get("reason") or ""),
        "before": row.get("before"),
        "after": row.get("after"),
        "meta": _safe_meta(row.get("meta") or {}),
    }


def _agent_ledger() -> list[dict]:
    return _AGENT_SERVICE.ledger()


class EconomicReadModel:
    def __init__(self, user_db_loader=None, agent_ledger_loader=None):
        self._user_db_loader = user_db_loader or state_manager.load_db
        self._agent_ledger_loader = agent_ledger_loader or _agent_ledger

    def events(
        self,
        *,
        limit: int = 100,
        domain: str | None = None,
        account_id: str | None = None,
    ) -> list[dict]:
        limit = int(limit)
        if limit < 1 or limit > 1000:
            raise ValueError("INVALID_LIMIT")

        db = self._user_db_loader()
        rows: list[dict] = []

        for row in db.get("ledger", []) if isinstance(db, dict) else []:
            if isinstance(row, dict):
                rows.append(normalize_user_event(row))

        for row in db.get("revenue_ledger", []) if isinstance(db, dict) else []:
            if isinstance(row, dict):
                rows.append(normalize_revenue_event(row))

        for row in self._agent_ledger_loader():
            if isinstance(row, dict):
                rows.append(normalize_agent_event(row))

        if domain:
            rows = [row for row in rows if row["domain"] == str(domain)]
        if account_id:
            rows = [row for row in rows if row["account_id"] == str(account_id)]

        rows.sort(key=lambda row: (row["timestamp"], row["domain"], row["operation_ref"]))
        return rows[-limit:]

    def summary(self) -> dict:
        rows = self.events(limit=1000)
        by_domain: dict[str, int] = {}
        by_currency: dict[str, float] = {}
        for row in rows:
            by_domain[row["domain"]] = by_domain.get(row["domain"], 0) + 1
            currency = row["currency"]
            by_currency[currency] = by_currency.get(currency, 0.0) + float(row["amount"])
        return {
            "events": len(rows),
            "by_domain": by_domain,
            "net_amount_by_currency": by_currency,
        }
