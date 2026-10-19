"""Atomic staking workflow authority.

All wallet + stake-position mutations are performed in one atomic DB update.
This module is the staking-specific mutation boundary; callers must not mutate
wallet or stake_positions directly.
"""

import math
import time
from datetime import datetime, timezone

import state_manager


_LEGACY_POSITION_STAKE_WINDOW_SECONDS = 5.0
_LEGACY_UNSTAKE_PAIR_WINDOW_SECONDS = 600.0
_LEDGER_EPSILON = 1e-6


def _as_float(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _ledger_epoch(row):
    """Return a ledger timestamp as epoch seconds, or None when unavailable."""
    value = row.get("time") if isinstance(row, dict) else None
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def _legacy_refund_evidence(db, uid, position):
    """Detect strong evidence of an earlier aggregate refund for this position.

    Before position-aware staking, /stake debited the aggregate wallet and then
    created a position separately. The old /unstake <amount> refunded aggregate
    Credits without marking that position unlocked. Match only an unlinked legacy
    stake created within seconds of this position and a later, exact inverse
    aggregate unstake (same amount and reversed staked_before/staked_after).
    This function is diagnostic only and never mutates state.
    """
    amount = _as_float(position.get("amount"))
    created_at = _as_float(position.get("created_at"))
    if amount is None or amount <= 0 or created_at is None:
        return None

    ledger = db.get("ledger", [])
    if not isinstance(ledger, list):
        return None

    for stake_index, stake_row in enumerate(ledger):
        if not isinstance(stake_row, dict) or str(stake_row.get("uid") or "") != str(uid):
            continue
        if stake_row.get("reason") != "staking:stake":
            continue

        stake_meta = stake_row.get("meta")
        if not isinstance(stake_meta, dict):
            continue
        if stake_meta.get("position_id"):
            continue
        if str(stake_meta.get("command") or "").lower() not in {"stake", "stake_lock"}:
            continue

        stake_amount = _as_float(stake_row.get("amount"))
        stake_time = _ledger_epoch(stake_row)
        staked_before = _as_float(stake_meta.get("staked_before"))
        staked_after = _as_float(stake_meta.get("staked_after"))
        if any(value is None for value in (stake_amount, stake_time, staked_before, staked_after)):
            continue
        if abs(stake_amount + amount) > _LEDGER_EPSILON:
            continue
        if abs(stake_time - created_at) > _LEGACY_POSITION_STAKE_WINDOW_SECONDS:
            continue
        if abs((staked_after - staked_before) - amount) > _LEDGER_EPSILON:
            continue

        for refund_index in range(stake_index + 1, len(ledger)):
            refund_row = ledger[refund_index]
            if not isinstance(refund_row, dict) or str(refund_row.get("uid") or "") != str(uid):
                continue
            if refund_row.get("reason") != "staking:unstake":
                continue

            refund_meta = refund_row.get("meta")
            if not isinstance(refund_meta, dict):
                continue
            if refund_meta.get("position_id"):
                continue
            if str(refund_meta.get("command") or "").lower() != "unstake":
                continue

            refund_amount = _as_float(refund_row.get("amount"))
            refund_time = _ledger_epoch(refund_row)
            refund_staked_before = _as_float(refund_meta.get("staked_before"))
            refund_staked_after = _as_float(refund_meta.get("staked_after"))
            if any(value is None for value in (
                refund_amount, refund_time, refund_staked_before, refund_staked_after
            )):
                continue
            if abs(refund_amount - amount) > _LEDGER_EPSILON:
                continue
            if refund_time < stake_time or refund_time - stake_time > _LEGACY_UNSTAKE_PAIR_WINDOW_SECONDS:
                continue
            if abs(refund_staked_before - staked_after) > _LEDGER_EPSILON:
                continue
            if abs(refund_staked_after - staked_before) > _LEDGER_EPSILON:
                continue

            return {
                "classification": "LEGACY_AGGREGATE_UNSTAKE_MAY_HAVE_REFUNDED_POSITION",
                "position_id": str(position.get("id") or ""),
                "amount": amount,
                "legacy_stake_index": stake_index,
                "legacy_stake_time": stake_row.get("time"),
                "legacy_unstake_index": refund_index,
                "legacy_unstake_time": refund_row.get("time"),
                "reason": "exact amount and aggregate staked totals reverse the legacy stake",
            }

    return None


def stake_locked(uid, amount, lock_days=30, meta=None, request_id=None):
    uid = str(uid)
    amount = float(amount)
    lock_days = int(lock_days)
    meta = dict(meta or {})
    request_id = str(request_id or '').strip()
    if len(request_id) > 200:
        raise ValueError('request_id too long')

    if amount <= 0:
        raise ValueError("amount must be positive")
    if lock_days <= 0:
        raise ValueError("lock_days must be positive")

    def mutate(db):
        users = db.setdefault("users", {})
        user = users.get(uid)
        if user is None:
            raise ValueError("user not found")

        wallet = user.setdefault("wallet", {})
        credits = float(wallet.get("credits", 0) or 0)
        staked = float(wallet.get("staked", 0) or 0)

        positions = db.setdefault('stake_positions', {})
        request_key = f'{uid}:{request_id}' if request_id else ''
        if request_key:
            requests = db.setdefault('staking_requests', {})
            existing = requests.get(request_key)
            if existing:
                existing_position = positions.get(existing.get('position_id'))
                return {
                    'status': 'duplicate',
                    'request_id': request_id,
                    'position': existing_position,
                    'credits': float(wallet.get('credits', 0) or 0),
                    'staked': float(wallet.get('staked', 0) or 0),
                }
        if credits < amount:
            raise ValueError("insufficient credits")
        now = time.time()
        position_id = f"sp_{int(now * 1000)}"
        while position_id in positions:
            now += 0.001
            position_id = f"sp_{int(now * 1000)}"

        wallet["credits"] = credits - amount
        wallet["staked"] = staked + amount
        positions[position_id] = {
            "id": position_id,
            "uid": uid,
            "amount": amount,
            "lock_days": lock_days,
            "created_at": now,
            "unlocks_at": now + lock_days * 86400,
            "status": "locked",
        }

        if request_key:
            db.setdefault('staking_requests', {})[request_key] = {
                'position_id': position_id,
                'uid': uid,
                'created_at': now,
            }

        db.setdefault('ledger', []).append({
            "time": datetime.now(timezone.utc).isoformat(),
            "uid": uid,
            "before": credits,
            "amount": -amount,
            "after": credits - amount,
            "reason": "staking:stake_locked",
            "meta": {
                **meta,
                "position_id": position_id,
                "lock_days": lock_days,
                "staked_before": staked,
                "staked_after": staked + amount,
            },
        })

        return {
            'status': 'completed',
            'request_id': request_id or None,
            'position': positions[position_id],
            "credits": credits - amount,
            "staked": staked + amount,
        }

    return state_manager.atomic_update(mutate)


def unstake_locked(uid, position_id, meta=None, request_id=None):
    uid = str(uid)
    position_id = str(position_id)
    meta = dict(meta or {})
    request_id = str(request_id or '').strip()
    if len(request_id) > 200:
        raise ValueError('request_id too long')

    def mutate(db):
        users = db.setdefault("users", {})
        user = users.get(uid)
        if user is None:
            raise ValueError("user not found")

        position = db.setdefault("stake_positions", {}).get(position_id)
        if not position or str(position.get("uid")) != uid:
            raise ValueError("position not found")
        request_key = f'{uid}:{request_id}' if request_id else ''
        if request_key:
            requests = db.setdefault('staking_unstake_requests', {})
            existing = requests.get(request_key)
            if existing:
                return {
                    'status': 'duplicate',
                    'request_id': request_id,
                    'position_id': existing.get('position_id', position_id),
                    'credits': float(user.setdefault('wallet', {}).get('credits', 0) or 0),
                    'staked': float(user.setdefault('wallet', {}).get('staked', 0) or 0),
                }
        if position.get('status') == 'unlocked':
            return {'status': 'duplicate', 'position_id': position_id, 'request_id': request_id or None}

        # Legacy /unstake <amount> refunded aggregate Credits but could leave
        # historical position records marked "locked". Fail closed only when
        # strong time/amount/staked-total evidence points to a prior refund.
        legacy_refund = _legacy_refund_evidence(db, uid, position)
        if legacy_refund:
            return {
                'status': 'legacy_refund_review_required',
                'position_id': position_id,
                'evidence': legacy_refund,
            }

        if time.time() < float(position.get("unlocks_at", 0)):
            raise ValueError("still locked")

        amount = float(position.get("amount", 0) or 0)
        if amount <= 0:
            raise ValueError("invalid position amount")

        wallet = user.setdefault("wallet", {})
        credits = float(wallet.get("credits", 0) or 0)
        staked = float(wallet.get("staked", 0) or 0)
        if staked < amount:
            raise ValueError("insufficient staked balance")

        wallet["staked"] = staked - amount
        wallet["credits"] = credits + amount
        position["status"] = "unlocked"
        position["unlocked_at"] = time.time()

        if request_key:
            db.setdefault('staking_unstake_requests', {})[request_key] = {
                'position_id': position_id,
                'uid': uid,
                'created_at': time.time(),
            }

        db.setdefault('ledger', []).append({
            "time": datetime.now(timezone.utc).isoformat(),
            "uid": uid,
            "before": credits,
            "amount": amount,
            "after": credits + amount,
            "reason": "staking:unstake_locked",
            "meta": {
                **meta,
                "position_id": position_id,
                "staked_before": staked,
                "staked_after": staked - amount,
            },
        })

        return {
            "status": "completed",
            "position": position,
            "credits": credits + amount,
            "staked": staked - amount,
        }

    return state_manager.atomic_update(mutate)
