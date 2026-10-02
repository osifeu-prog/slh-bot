"""Governed secondary BSC distribution-wallet registry.

A secondary distribution wallet is an external, user-controlled BSC wallet that
has already completed Telegram -> BNB ownership verification. Registration here
does not move funds, import keys, or grant server custody. It only records an
OWNER-approved distribution role and explicit limits for later user-signed
distribution preparation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from web3 import Web3

import state_manager
from core.authority import is_owner
from core.binance_connector import get_bsc_config
from core.wallet_binding import get_binding

REGISTRY_KEY = "secondary_distribution_wallets"
AUDIT_KEY = "secondary_distribution_wallet_audit"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _limit(value: Any, field: str) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"INVALID_{field.upper()}") from exc
    if not amount.is_finite() or amount <= 0:
        raise ValueError(f"INVALID_{field.upper()}")
    return amount


def _target_uid(uid: Any) -> str:
    value = str(uid or "").strip()
    if not value.isdigit() or int(value) <= 0:
        raise ValueError("INVALID_USER_ID")
    return value


def _bsc_config() -> dict[str, Any]:
    db = state_manager.load_db()
    cfg = dict(get_bsc_config())
    overrides = db.get("bsc_settings") if isinstance(db, dict) else None
    if isinstance(overrides, dict):
        cfg.update(overrides)
    return cfg


def get_secondary_distribution_wallet(uid: Any) -> dict[str, Any] | None:
    target = _target_uid(uid)
    db = state_manager.load_db()
    record = (db.get(REGISTRY_KEY, {}) or {}).get(target)
    return dict(record) if isinstance(record, dict) else None


def list_secondary_distribution_wallets() -> list[dict[str, Any]]:
    db = state_manager.load_db()
    raw = db.get(REGISTRY_KEY, {}) if isinstance(db, dict) else {}
    rows = [dict(value) for value in raw.values() if isinstance(value, dict)]
    rows.sort(key=lambda row: str(row.get("enabled_at") or row.get("updated_at") or ""))
    return rows


def set_secondary_distribution_wallet(
    owner_id: Any,
    target_uid: Any,
    *,
    per_tx_limit: Any = None,
    daily_limit: Any = None,
    limit_mode: str = "bounded",
) -> dict[str, Any]:
    """OWNER-gated registration of an already verified BSC wallet.

    The wallet must be the target user's current verified BNB binding. This
    operation only mutates registry/audit metadata; it never mutates balances.
    """
    if not is_owner(owner_id):
        raise PermissionError("OWNER_ONLY")

    target = _target_uid(target_uid)
    mode = str(limit_mode or "bounded").strip().lower()
    if mode not in {"bounded", "unbounded"}:
        raise ValueError("INVALID_LIMIT_MODE")
    if mode == "unbounded":
        per_tx = daily = None
    else:
        per_tx = _limit(per_tx_limit, "PER_TX_LIMIT")
        daily = _limit(daily_limit, "DAILY_LIMIT")
        if daily < per_tx:
            raise ValueError("DAILY_LIMIT_BELOW_PER_TX_LIMIT")

    binding = get_binding(target)
    if not binding:
        raise ValueError("BNB_WALLET_NOT_VERIFIED")

    address = Web3.to_checksum_address(str(binding.get("address") or ""))
    cfg = _bsc_config()
    token_contract = str(cfg.get("token_contract") or "").strip()
    if not token_contract or not Web3.is_address(token_contract):
        raise ValueError("SLH_TOKEN_NOT_CONFIGURED")
    token_contract = Web3.to_checksum_address(token_contract)

    owner = str(owner_id)
    now = _now()

    def mutate(db: dict) -> dict:
        registry = db.setdefault(REGISTRY_KEY, {})

        for uid, current in registry.items():
            if str(uid) == target or not isinstance(current, dict):
                continue
            if (
                current.get("status") == "active"
                and str(current.get("address", "")).lower() == address.lower()
            ):
                raise ValueError("WALLET_ALREADY_REGISTERED_AS_SECONDARY")

        previous = registry.get(target)
        record = {
            "uid": target,
            "chain": "bsc",
            "chain_id": 56,
            "address": address,
            "role": "secondary_distribution_wallet",
            "status": "active",
            "mode": "user_signed_only",
            "asset": "SLH",
            "token_contract": token_contract,
            "limit_mode": mode,
            "per_tx_limit_slh": str(per_tx) if per_tx is not None else None,
            "daily_limit_slh": str(daily) if daily is not None else None,
            "enabled_by": owner,
            "enabled_at": now,
            "binding_verified": True,
        }
        registry[target] = record

        db.setdefault(AUDIT_KEY, []).append(
            {
                "event": "secondary_distribution_wallet_enabled",
                "uid": target,
                "address": address,
                "enabled_by": owner,
                "enabled_at": now,
                "previous_status": previous.get("status") if isinstance(previous, dict) else None,
                "limit_mode": mode,
                "per_tx_limit_slh": str(per_tx) if per_tx is not None else None,
                "daily_limit_slh": str(daily) if daily is not None else None,
                "token_contract": token_contract,
                "funds_moved": False,
                "custody_granted": False,
            }
        )
        return dict(record)

    return state_manager.atomic_update(mutate)


def revoke_secondary_distribution_wallet(owner_id: Any, target_uid: Any) -> dict[str, Any]:
    if not is_owner(owner_id):
        raise PermissionError("OWNER_ONLY")

    target = _target_uid(target_uid)
    now = _now()

    def mutate(db: dict) -> dict:
        registry = db.setdefault(REGISTRY_KEY, {})
        record = registry.get(target)
        if not isinstance(record, dict):
            raise ValueError("SECONDARY_DISTRIBUTION_WALLET_NOT_FOUND")
        record = dict(record)
        record["status"] = "revoked"
        record["revoked_by"] = str(owner_id)
        record["revoked_at"] = now
        registry[target] = record
        db.setdefault(AUDIT_KEY, []).append(
            {
                "event": "secondary_distribution_wallet_revoked",
                "uid": target,
                "address": record.get("address"),
                "revoked_by": str(owner_id),
                "revoked_at": now,
                "funds_moved": False,
                "custody_granted": False,
            }
        )
        return record

    return state_manager.atomic_update(mutate)
