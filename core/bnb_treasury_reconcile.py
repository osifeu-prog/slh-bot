"""Owner-confirmed repair of stale BSC Treasury configuration.

This flow only aligns the persisted Treasury address with the Railway-provided
SLH_BSC_CANONICAL_TREASURY. It never opens settlement, sends transactions, or
changes balances/ledgers. BNB_DEPOSITS_OPEN must be explicitly set to "0".
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import os
import uuid

from web3 import Web3

import state_manager
from core.authority import is_owner
from core.bsc_address_policy import is_quarantined_bsc_address

PENDING_KEY = "bnb_treasury_reconcile_pending"
AUDIT_KEY = "bnb_treasury_reconcile_audit"
TTL_SECONDS = 300
AUDIT_LIMIT = 50

_ADDRESS_BLOCKERS = {
    "BNB_CANONICAL_TREASURY_MISSING",
    "BNB_CANONICAL_TREASURY_MISMATCH",
    "BNB_CANONICAL_TREASURY_QUARANTINED_ZUZ",
    "BNB_TREASURY_QUARANTINED_ZUZ",
    "BNB_TREASURY_MATCHES_BOUND_WALLET",
    "BNB_WALLET_BINDINGS_UNVERIFIED",
}


def _utc_now(value=None):
    if value is None:
        value = datetime.now(timezone.utc)
    elif isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if not isinstance(value, datetime):
        raise TypeError("BNB_TREASURY_RECONCILE_TIME_INVALID")
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _utc_text(value=None):
    return _utc_now(value).isoformat()


def _gate_flag_closed():
    return str(os.getenv("BNB_DEPOSITS_OPEN", "0")).strip() == "0"


def _canonical_target():
    raw = str(os.getenv("SLH_BSC_CANONICAL_TREASURY", "") or "").strip()
    if not raw:
        return None, "BNB_CANONICAL_TREASURY_MISSING"
    if not Web3.is_address(raw):
        return None, "BNB_CANONICAL_TREASURY_INVALID"
    try:
        target = Web3.to_checksum_address(raw)
    except Exception:
        return None, "BNB_CANONICAL_TREASURY_INVALID"
    if is_quarantined_bsc_address(target):
        return None, "BNB_CANONICAL_TREASURY_QUARANTINED_ZUZ"
    return target, None


def _effective_config(db):
    from core.bnb_gate import _effective_config as get_effective_config

    return get_effective_config(db)


def _address_blocker_for_target(db, target):
    """Validate target against canonical env + every bound BSC wallet."""
    if not isinstance(db, dict):
        return "BNB_DB_UNREADABLE"
    if not isinstance(db.get("wallet_bindings"), dict):
        return "BNB_WALLET_BINDINGS_UNVERIFIED"
    proposed = deepcopy(db)
    settings = proposed.get("bsc_settings")
    if not isinstance(settings, dict):
        settings = {}
        proposed["bsc_settings"] = settings
    settings["treasury_wallet"] = target

    try:
        from core.bnb_gate import bnb_readiness

        reasons = set(bnb_readiness(proposed).get("reasons") or [])
    except Exception:
        return "BNB_TREASURY_VALIDATION_UNAVAILABLE"
    for code in (
        "BNB_CANONICAL_TREASURY_MISSING",
        "BNB_CANONICAL_TREASURY_MISMATCH",
        "BNB_CANONICAL_TREASURY_QUARANTINED_ZUZ",
        "BNB_TREASURY_QUARANTINED_ZUZ",
        "BNB_TREASURY_MATCHES_BOUND_WALLET",
        "BNB_WALLET_BINDINGS_UNVERIFIED",
    ):
        if code in reasons:
            return code
    return None


def _append_audit(db, record, status, *, detail="", now=None):
    rows = db.get(AUDIT_KEY)
    if not isinstance(rows, list):
        rows = []
        db[AUDIT_KEY] = rows
    rows.append({
        "audit_id": uuid.uuid4().hex,
        "reconcile_id": str(record.get("confirmation_id") or ""),
        "actor_uid": str(record.get("uid") or ""),
        "status": str(status),
        "previous_treasury": str(record.get("previous_treasury") or ""),
        "canonical_treasury": str(record.get("canonical_treasury") or ""),
        "at": _utc_text(now),
        "detail": str(detail or "")[:120],
        "public_gate_changed": False,
        "financial_ledger_changed": False,
    })
    del rows[:-AUDIT_LIMIT]


def inspect_bnb_treasury_reconcile(uid):
    """Read-only Treasury config diagnostic for the verified owner."""
    uid = str(uid or "").strip()
    if not is_owner(uid):
        return {"status": "FORBIDDEN"}
    try:
        db = state_manager.load_db()
        cfg = _effective_config(db)
    except Exception:
        return {"status": "BLOCKED", "code": "BNB_TREASURY_CONFIG_READ_FAILED"}
    target, code = _canonical_target()
    current = str(cfg.get("treasury_wallet") or "").strip()
    blocker = code or _address_blocker_for_target(db, target)
    if not _gate_flag_closed():
        blocker = blocker or "BNB_DEPOSITS_OPEN_FLAG_NOT_ZERO"
    if blocker:
        return {
            "status": "BLOCKED",
            "code": blocker,
            "current_treasury": current,
            "canonical_treasury": target or "",
            "public_bnb_gate": "CLOSED" if not _gate_flag_closed() or os.getenv("BNB_DEPOSITS_OPEN", "0").strip() == "0" else "UNVERIFIED",
        }
    return {
        "status": "ALREADY_CANONICAL" if current.lower() == target.lower() else "CONFIG_MISMATCH",
        "current_treasury": current,
        "canonical_treasury": target,
        "public_bnb_gate": "CLOSED",
        "next_action": "none" if current.lower() == target.lower() else "prepare_owner_confirmed_reconcile",
    }


def prepare_bnb_treasury_reconcile(uid, *, now=None):
    """Create an expiring, owner-only preview; do not change configuration."""
    uid = str(uid or "").strip()
    if not is_owner(uid):
        return {"status": "FORBIDDEN"}
    if not _gate_flag_closed():
        return {"status": "BLOCKED", "code": "BNB_DEPOSITS_OPEN_FLAG_NOT_ZERO"}
    try:
        db = state_manager.load_db()
        if not isinstance(db, dict):
            return {"status": "BLOCKED", "code": "BNB_DB_UNREADABLE"}
        current = str(_effective_config(db).get("treasury_wallet") or "").strip()
    except Exception:
        return {"status": "BLOCKED", "code": "BNB_TREASURY_CONFIG_READ_FAILED"}

    target, code = _canonical_target()
    if code:
        return {"status": "BLOCKED", "code": code}
    blocker = _address_blocker_for_target(db, target)
    if blocker:
        return {"status": "BLOCKED", "code": blocker}
    if current.lower() == target.lower():
        return {
            "status": "ALREADY_CANONICAL",
            "current_treasury": current,
            "canonical_treasury": target,
            "public_bnb_gate": "CLOSED",
        }

    current_time = _utc_now(now)
    record = {
        "confirmation_id": uuid.uuid4().hex[:12],
        "uid": uid,
        "previous_treasury": current,
        "canonical_treasury": target,
        "created_at": current_time.isoformat(),
        "expires_at": (current_time + timedelta(seconds=TTL_SECONDS)).isoformat(),
        "status": "PREPARED",
    }

    def mutate(live_db):
        if not isinstance(live_db, dict):
            return {"status": "BLOCKED", "code": "BNB_DB_UNREADABLE"}
        if not _gate_flag_closed():
            return {"status": "BLOCKED", "code": "BNB_DEPOSITS_OPEN_FLAG_NOT_ZERO"}
        live_target, target_error = _canonical_target()
        if target_error or live_target.lower() != target.lower():
            return {"status": "BLOCKED", "code": "BNB_CANONICAL_TREASURY_CHANGED"}
        live_current = str(_effective_config(live_db).get("treasury_wallet") or "").strip()
        if live_current.lower() != current.lower():
            return {"status": "BLOCKED", "code": "BNB_TREASURY_CHANGED_BEFORE_PREVIEW"}
        live_blocker = _address_blocker_for_target(live_db, target)
        if live_blocker:
            return {"status": "BLOCKED", "code": live_blocker}
        pending = live_db.setdefault(PENDING_KEY, {})
        if not isinstance(pending, dict):
            return {"status": "BLOCKED", "code": "BNB_TREASURY_PENDING_INVALID"}
        pending[uid] = record
        _append_audit(live_db, record, "PREPARED", now=current_time)
        return {
            "status": "PREPARED",
            "confirmation_id": record["confirmation_id"],
            "previous_treasury": current,
            "canonical_treasury": target,
            "expires_at": record["expires_at"],
            "public_bnb_gate": "CLOSED",
        }

    try:
        return state_manager.atomic_update(mutate)
    except Exception:
        return {"status": "BLOCKED", "code": "BNB_TREASURY_PREVIEW_WRITE_FAILED"}


def confirm_bnb_treasury_reconcile(uid, confirmation_id=None, *, now=None):
    """Apply the previewed config-only repair after fresh explicit owner approval."""
    uid = str(uid or "").strip()
    if not is_owner(uid):
        return {"status": "FORBIDDEN"}
    if not _gate_flag_closed():
        return {"status": "BLOCKED", "code": "BNB_DEPOSITS_OPEN_FLAG_NOT_ZERO"}

    try:
        live = state_manager.load_db()
        pending = live.get(PENDING_KEY, {}) if isinstance(live, dict) else {}
        record = pending.get(uid) if isinstance(pending, dict) else None
    except Exception:
        return {"status": "BLOCKED", "code": "BNB_TREASURY_PENDING_READ_FAILED"}
    if not isinstance(record, dict):
        return {"status": "NOT_PENDING"}
    supplied_id = str(confirmation_id or record.get("confirmation_id") or "").strip()
    if supplied_id != str(record.get("confirmation_id") or ""):
        return {"status": "NOT_PENDING"}
    current_time = _utc_now(now)
    try:
        expires_at = _utc_now(record.get("expires_at"))
    except Exception:
        return {"status": "BLOCKED", "code": "BNB_TREASURY_PREVIEW_INVALID"}
    if current_time > expires_at:
        def expire(db):
            rows = db.get(PENDING_KEY, {}) if isinstance(db, dict) else {}
            item = rows.get(uid) if isinstance(rows, dict) else None
            if isinstance(item, dict) and item.get("confirmation_id") == supplied_id:
                rows.pop(uid, None)
                _append_audit(db, item, "EXPIRED", now=current_time)
            return {"status": "EXPIRED"}
        try:
            return state_manager.atomic_update(expire)
        except Exception:
            return {"status": "EXPIRED"}

    expected_target, target_error = _canonical_target()
    if target_error or expected_target.lower() != str(record.get("canonical_treasury") or "").lower():
        return {"status": "BLOCKED", "code": "BNB_CANONICAL_TREASURY_CHANGED_AFTER_PREVIEW"}
    try:
        live_current = str(_effective_config(live).get("treasury_wallet") or "").strip()
    except Exception:
        return {"status": "BLOCKED", "code": "BNB_TREASURY_CONFIG_READ_FAILED"}
    if live_current.lower() != str(record.get("previous_treasury") or "").lower():
        return {"status": "BLOCKED", "code": "BNB_TREASURY_CHANGED_AFTER_PREVIEW"}
    blocker = _address_blocker_for_target(live, expected_target)
    if blocker:
        return {"status": "BLOCKED", "code": blocker}

    def mutate(db):
        if not isinstance(db, dict):
            return {"status": "BLOCKED", "code": "BNB_DB_UNREADABLE"}
        if not _gate_flag_closed():
            return {"status": "BLOCKED", "code": "BNB_DEPOSITS_OPEN_FLAG_NOT_ZERO"}
        rows = db.get(PENDING_KEY, {})
        item = rows.get(uid) if isinstance(rows, dict) else None
        if not isinstance(item, dict) or item.get("confirmation_id") != supplied_id:
            return {"status": "NOT_PENDING"}
        if _utc_now(item.get("expires_at")) < current_time:
            rows.pop(uid, None)
            _append_audit(db, item, "EXPIRED", now=current_time)
            return {"status": "EXPIRED"}
        target_now, target_error_now = _canonical_target()
        if target_error_now or target_now.lower() != expected_target.lower():
            return {"status": "BLOCKED", "code": "BNB_CANONICAL_TREASURY_CHANGED_AFTER_PREVIEW"}
        current_now = str(_effective_config(db).get("treasury_wallet") or "").strip()
        if current_now.lower() != str(item.get("previous_treasury") or "").lower():
            return {"status": "BLOCKED", "code": "BNB_TREASURY_CHANGED_AFTER_PREVIEW"}
        final_blocker = _address_blocker_for_target(db, target_now)
        if final_blocker:
            return {"status": "BLOCKED", "code": final_blocker}
        settings = db.get("bsc_settings")
        if not isinstance(settings, dict):
            settings = {}
            db["bsc_settings"] = settings
        settings["treasury_wallet"] = target_now
        rows.pop(uid, None)
        _append_audit(db, item, "RECONCILED", now=current_time)
        return {
            "status": "RECONCILED",
            "previous_treasury": current_now,
            "treasury_wallet": target_now,
            "public_bnb_gate": "CLOSED",
            "changed_settings": ["bsc_settings.treasury_wallet"],
            "financial_ledger_changed": False,
            "wallet_balances_changed": False,
            "transaction_sent": False,
        }

    try:
        result = state_manager.atomic_update(mutate)
    except Exception:
        return {"status": "BLOCKED", "code": "BNB_TREASURY_RECONCILE_WRITE_FAILED"}
    if not isinstance(result, dict) or result.get("status") != "RECONCILED":
        return result if isinstance(result, dict) else {"status": "BLOCKED", "code": "BNB_TREASURY_RECONCILE_RESULT_INVALID"}

    try:
        from core.bnb_gate import _effective_config as effective_config, bnb_deposits_open

        after = state_manager.load_db()
        after_target = str(effective_config(after).get("treasury_wallet") or "").strip()
        if after_target.lower() != expected_target.lower():
            return {"status": "VERIFY_FAILED", "code": "BNB_TREASURY_RECONCILE_VERIFY_FAILED"}
        if bnb_deposits_open():
            return {"status": "VERIFY_FAILED", "code": "BNB_PUBLIC_GATE_UNEXPECTEDLY_OPEN"}
    except Exception:
        return {"status": "VERIFY_FAILED", "code": "BNB_TREASURY_RECONCILE_VERIFY_FAILED"}
    return result
