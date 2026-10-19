"""Atomic staking workflow authority.

All wallet + stake-position mutations are performed in one atomic DB update.
This module is the staking-specific mutation boundary; callers must not mutate
wallet or stake_positions directly.
"""

import math
import time
from datetime import datetime, timezone

import state_manager


_LEGACY_UNSTAKE_AMBIGUITY_WINDOW_SECONDS = 300.0
_LEDGER_EPSILON = 1e-6


def _as_float(value):
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _ledger_epoch(row):
    """Return a ledger timestamp as epoch seconds, or None when unavailable."""
    value = row.get("time") if isinstance(row, dict) else None
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(float(value)) else None
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except (TypeError, ValueError, OverflowError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    timestamp = parsed.timestamp()
    return timestamp if math.isfinite(timestamp) else None


def _find_legacy_unstake_ambiguity(db, uid, position):
    """Find same-amount unlinked legacy unstake within five minutes of creation.

    Old aggregate /unstake rows have no position_id. If a legacy row for the
    same user and amount falls close to the position's creation time, allocation
    cannot be proven, so the service must fail closed and request human review.
    A larger withdrawal or an equal amount days later is not enough evidence.
    This function is read-only.
    """
    if not isinstance(position, dict):
        return None
    amount = _as_float(position.get("amount"))
    created_at = _as_float(position.get("created_at"))
    if amount is None or amount <= 0 or created_at is None:
        return None

    ledger = db.get("ledger", [])
    if not isinstance(ledger, list):
        return None

    for index, row in enumerate(ledger):
        if not isinstance(row, dict) or str(row.get("uid") or "") != str(uid):
            continue
        if row.get("reason") != "staking:unstake":
            continue

        meta = row.get("meta")
        if not isinstance(meta, dict):
            meta = {}
        if meta.get("position_id"):
            continue

        refund_amount = _as_float(row.get("amount"))
        refund_time = _ledger_epoch(row)
        if refund_amount is None or refund_time is None:
            continue
        if abs(refund_amount - amount) > _LEDGER_EPSILON:
            continue

        delta = abs(refund_time - created_at)
        if delta > _LEGACY_UNSTAKE_AMBIGUITY_WINDOW_SECONDS:
            continue

        return {
            "code": "LEGACY_UNSTAKE_AMBIGUITY",
            "ledger_index": index,
            "ledger_time": row.get("time"),
            "ledger_amount": refund_amount,
            "position_id": str(position.get("id") or ""),
            "position_amount": amount,
            "position_created_at": created_at,
            "seconds_from_creation": round(delta, 6),
            "reason": "same user, same amount, legacy row without position_id within five minutes",
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

        wallet = user.setdefault("wallet", {})
        credits = float(wallet.get("credits", 0) or 0)
        staked = float(wallet.get("staked", 0) or 0)
        requests = db.setdefault("staking_unstake_requests", {})
        idempotency_key = f"unstake:{position_id}"

        # One stable key per position prevents retries from producing another payout.
        if idempotency_key in requests:
            return {
                "status": "already_unlocked",
                "position_id": position_id,
                "credits": credits,
                "staked": staked,
            }

        request_key = f"{uid}:{request_id}" if request_id else ""
        if request_key and request_key in requests:
            existing = requests[request_key]
            if str(existing.get("position_id") or "") == position_id:
                return {
                    "status": "already_unlocked",
                    "position_id": position_id,
                    "credits": credits,
                    "staked": staked,
                }
            return {
                "status": "duplicate",
                "position_id": str(existing.get("position_id") or ""),
                "credits": credits,
                "staked": staked,
            }

        # Fail closed when position state is inconsistent; never infer a refund.
        if position.get("status") == "unlocked" or position.get("unlocked_at") is not None:
            return {
                "status": "already_unlocked",
                "position_id": position_id,
                "credits": credits,
                "staked": staked,
            }
        if position.get("status") != "locked":
            return {
                "status": "position_state_review_required",
                "position_id": position_id,
                "credits": credits,
                "staked": staked,
            }

        # Same amount + same user + legacy row without position_id near creation:
        # require manual review before performing any financial/state mutation.
        legacy = _find_legacy_unstake_ambiguity(db, uid, position)
        if legacy is not None:
            return {
                "status": "legacy_refund_review_required",
                "position_id": position_id,
                "code": "LEGACY_UNSTAKE_AMBIGUITY",
                "evidence": legacy,
                "credits": credits,
                "staked": staked,
            }

        now = time.time()
        try:
            unlocks_at = float(position.get("unlocks_at", 0) or 0)
        except (TypeError, ValueError, OverflowError):
            raise ValueError("invalid position unlock time")
        if not math.isfinite(unlocks_at):
            raise ValueError("invalid position unlock time")
        if now < unlocks_at:
            raise ValueError("still locked")

        amount = _as_float(position.get("amount"))
        if amount is None or amount <= 0:
            raise ValueError("invalid position amount")
        if staked < amount:
            raise ValueError("insufficient staked balance")

        # Atomic mutation: position, wallet, idempotency record, and ledger row.
        wallet["staked"] = staked - amount
        wallet["credits"] = credits + amount
        position["status"] = "unlocked"
        position["unlocked_at"] = now

        requests[idempotency_key] = {
            "position_id": position_id,
            "uid": uid,
            "created_at": now,
            "idempotency_key": idempotency_key,
        }
        if request_key:
            requests[request_key] = {
                "position_id": position_id,
                "uid": uid,
                "created_at": now,
                "idempotency_key": idempotency_key,
            }

        db.setdefault("ledger", []).append({
            "time": datetime.now(timezone.utc).isoformat(),
            "uid": uid,
            "before": credits,
            "amount": amount,
            "after": credits + amount,
            "reason": "staking:unstake_locked",
            "meta": {
                **meta,
                "position_id": position_id,
                "idempotency_key": idempotency_key,
                "staked_before": staked,
                "staked_after": staked - amount,
                "legacy_guard": "checked",
            },
        })

        return {
            "status": "completed",
            "position": position,
            "credits": credits + amount,
            "staked": staked - amount,
            "idempotency_key": idempotency_key,
        }

    return state_manager.atomic_update(mutate)
