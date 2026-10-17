"""Atomic staking workflow authority.

All wallet + stake-position mutations are performed in one atomic DB update.
This module is the staking-specific mutation boundary; callers must not mutate
wallet or stake_positions directly.
"""

import math
import time
from datetime import datetime, timezone

import state_manager


def stake_locked(uid, amount, lock_days=30, meta=None, request_id=None):
    uid = str(uid)
    try:
        amount = float(amount)
        lock_days = int(lock_days)
    except (TypeError, ValueError, OverflowError):
        raise ValueError("INVALID_STAKING_REQUEST") from None
    meta = dict(meta or {})
    request_id = str(request_id or '').strip()
    if len(request_id) > 200:
        raise ValueError('request_id too long')

    if not math.isfinite(amount) or amount <= 0:
        raise ValueError("amount must be a finite positive number")
    if lock_days <= 0:
        raise ValueError("lock_days must be positive")

    def mutate(db):
        users = db.setdefault("users", {})
        user = users.get(uid)
        if not isinstance(user, dict):
            raise ValueError("user not found")

        requests = db.get("staking_requests", {})
        positions = db.get("stake_positions", {})
        ledger = db.get("ledger", [])
        if not isinstance(requests, dict):
            raise ValueError("STAKING_REQUEST_STORE_INVALID")
        if not isinstance(positions, dict):
            raise ValueError("INVALID_STAKE_POSITIONS")
        if not isinstance(ledger, list):
            raise ValueError("INVALID_LEDGER_STATE")

        request_key = f'{uid}:{request_id}' if request_id else ''
        if request_key:
            existing = requests.get(request_key)
            if existing:
                positions = db.get('stake_positions', {})
                existing_position = (
                    positions.get(existing.get('position_id'))
                    if isinstance(positions, dict)
                    else None
                )
                if not isinstance(existing_position, dict):
                    raise ValueError("STAKING_REQUEST_IDENTITY_UNKNOWN")
                try:
                    stored_amount = float(existing_position.get("amount"))
                    stored_lock_days = int(existing_position.get("lock_days"))
                except (TypeError, ValueError, OverflowError):
                    raise ValueError("STAKING_REQUEST_IDENTITY_UNKNOWN") from None
                if (
                    not math.isfinite(stored_amount)
                    or str(existing_position.get("uid") or "") != uid
                    or str(existing.get("uid") or "") != uid
                ):
                    raise ValueError("STAKING_REQUEST_IDENTITY_UNKNOWN")
                if (
                    not math.isclose(stored_amount, amount, rel_tol=0.0, abs_tol=1e-9)
                    or stored_lock_days != lock_days
                ):
                    raise ValueError("STAKING_REQUEST_IDENTITY_CONFLICT")
                wallet_value = user.get("wallet")
                if wallet_value is not None and not isinstance(wallet_value, dict):
                    raise ValueError("INVALID_WALLET_STATE")
                wallet = wallet_value if isinstance(wallet_value, dict) else {}
                try:
                    credits_now = float(wallet.get('credits', 0) or 0)
                    staked_now = float(wallet.get('staked', 0) or 0)
                except (TypeError, ValueError, OverflowError):
                    raise ValueError("INVALID_WALLET_BALANCE") from None
                if not math.isfinite(credits_now) or not math.isfinite(staked_now):
                    raise ValueError("INVALID_WALLET_BALANCE")
                return {
                    'status': 'duplicate',
                    'request_id': request_id,
                    'position': existing_position,
                    'credits': credits_now,
                    'staked': staked_now,
                }

        # Freeze applies to new staking debits, but not to an exact retry of
        # an already-created request above.
        if user.get("frozen") is True:
            raise ValueError("ACCOUNT_FROZEN")

        wallet_value = user.get("wallet")
        if wallet_value is not None and not isinstance(wallet_value, dict):
            raise ValueError("INVALID_WALLET_STATE")
        wallet = wallet_value if isinstance(wallet_value, dict) else {}
        try:
            credits = float(wallet.get("credits", 0) or 0)
            staked = float(wallet.get("staked", 0) or 0)
        except (TypeError, ValueError, OverflowError):
            raise ValueError("INVALID_WALLET_BALANCE") from None
        if not math.isfinite(credits) or not math.isfinite(staked) or credits < 0 or staked < 0:
            raise ValueError("INVALID_WALLET_BALANCE")

        if credits < amount:
            raise ValueError("insufficient credits")
        now = time.time()
        position_id = f"sp_{int(now * 1000)}"
        while position_id in positions:
            now += 0.001
            position_id = f"sp_{int(now * 1000)}"

        # All store shapes and financial checks passed; attach default stores
        # only on the successful mutation path.
        positions = db.setdefault("stake_positions", positions)
        if request_key:
            requests = db.setdefault("staking_requests", requests)
        ledger = db.setdefault("ledger", ledger)
        if wallet_value is None:
            user["wallet"] = wallet
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
            requests = db.setdefault('staking_requests', {})
            requests[request_key] = {
                'position_id': position_id,
                'uid': uid,
                'amount': amount,
                'lock_days': lock_days,
                'created_at': now,
            }

        ledger.append({
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
        users = db.get("users")
        user = users.get(uid) if isinstance(users, dict) else None
        if not isinstance(user, dict):
            raise ValueError("user not found")

        positions = db.get("stake_positions")
        position = positions.get(position_id) if isinstance(positions, dict) else None
        if not isinstance(position, dict) or str(position.get("uid") or "") != uid:
            raise ValueError("position not found")
        ledger = db.get("ledger", [])
        if not isinstance(ledger, list):
            raise ValueError("INVALID_LEDGER_STATE")

        request_key = f'{uid}:{request_id}' if request_id else ''
        if request_key:
            requests = db.get('staking_unstake_requests', {})
            if not isinstance(requests, dict):
                raise ValueError("STAKING_UNSTAKE_REQUEST_STORE_INVALID")
            existing = requests.get(request_key)
            if existing:
                if not isinstance(existing, dict):
                    raise ValueError("STAKING_UNSTAKE_IDENTITY_UNKNOWN")
                stored_position_id = str(existing.get("position_id") or "").strip()
                stored_uid = str(existing.get("uid") or "").strip()
                if not stored_position_id or not stored_uid:
                    raise ValueError("STAKING_UNSTAKE_IDENTITY_UNKNOWN")
                if stored_uid != uid:
                    raise ValueError("STAKING_UNSTAKE_IDENTITY_UNKNOWN")
                if stored_position_id != position_id:
                    raise ValueError("STAKING_UNSTAKE_IDENTITY_CONFLICT")
                wallet_value = user.get("wallet")
                if wallet_value is not None and not isinstance(wallet_value, dict):
                    raise ValueError("INVALID_WALLET_STATE")
                wallet = wallet_value if isinstance(wallet_value, dict) else {}
                try:
                    credits_now = float(wallet.get('credits', 0) or 0)
                    staked_now = float(wallet.get('staked', 0) or 0)
                except (TypeError, ValueError, OverflowError):
                    raise ValueError("INVALID_WALLET_BALANCE") from None
                if not math.isfinite(credits_now) or not math.isfinite(staked_now):
                    raise ValueError("INVALID_WALLET_BALANCE")
                return {
                    'status': 'duplicate',
                    'request_id': request_id,
                    'position_id': stored_position_id,
                    'credits': credits_now,
                    'staked': staked_now,
                }

        if position.get('status') == 'unlocked':
            return {'status': 'duplicate', 'position_id': position_id, 'request_id': request_id or None}

        try:
            unlocks_at = float(position.get("unlocks_at", 0))
        except (TypeError, ValueError, OverflowError):
            raise ValueError("INVALID_STAKE_POSITION") from None
        if not math.isfinite(unlocks_at) or unlocks_at < 0:
            raise ValueError("INVALID_STAKE_POSITION")
        if time.time() < unlocks_at:
            raise ValueError("still locked")

        try:
            amount = float(position.get("amount", 0) or 0)
        except (TypeError, ValueError, OverflowError):
            raise ValueError("invalid position amount") from None
        if not math.isfinite(amount) or amount <= 0:
            raise ValueError("invalid position amount")

        wallet_value = user.get("wallet")
        if wallet_value is not None and not isinstance(wallet_value, dict):
            raise ValueError("INVALID_WALLET_STATE")
        wallet = wallet_value if isinstance(wallet_value, dict) else {}
        try:
            credits = float(wallet.get("credits", 0) or 0)
            staked = float(wallet.get("staked", 0) or 0)
        except (TypeError, ValueError, OverflowError):
            raise ValueError("INVALID_WALLET_BALANCE") from None
        if not math.isfinite(credits) or not math.isfinite(staked) or credits < 0 or staked < 0:
            raise ValueError("INVALID_WALLET_BALANCE")
        if staked < amount:
            raise ValueError("insufficient staked balance")

        # Attach missing stores only after all request, balance and
        # position checks have passed, so rejected calls leave state unchanged.
        ledger = db.setdefault("ledger", ledger)
        if request_key:
            requests = db.setdefault("staking_unstake_requests", {})
        if wallet_value is None:
            user["wallet"] = wallet
        wallet["staked"] = staked - amount
        wallet["credits"] = credits + amount
        position["status"] = "unlocked"
        position["unlocked_at"] = time.time()

        if request_key:
            requests[request_key] = {
                'position_id': position_id,
                'uid': uid,
                'created_at': time.time(),
            }

        ledger.append({
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
