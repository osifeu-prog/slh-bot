"""Isolated paper AMM for SLH Spark alpha.

All balances live under db["paper_simulation"]. This module never reads or
writes the canonical Credits wallet, canonical ledger, live exchange orders,
on-chain wallets, or execution/deposit gates.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_DOWN
import hashlib
from typing import Any

import state_manager

DB_KEY = "paper_simulation"
QUANT = Decimal("0.00000001")
ZERO = Decimal("0")
STARTING_CREDITS = Decimal("1000")
STARTING_SLH = Decimal("1000")
INITIAL_POOL_CREDITS = Decimal("1000000")
INITIAL_POOL_SLH = Decimal("1000000")
FEE_RATE = Decimal("0.003")
MIN_AMOUNT = Decimal("0.01")
MAX_AMOUNT = Decimal("100000")
MAX_TRADES = 5000
MAX_REQUESTS_PER_USER = 1000


def _now(now: str | None = None) -> str:
    return str(now or datetime.now(timezone.utc).isoformat())


def _d(value: Any) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise InvalidOperation
    result = Decimal(str(value))
    if not result.is_finite():
        raise InvalidOperation
    return result


def _q(value: Decimal) -> Decimal:
    return value.quantize(QUANT, rounding=ROUND_DOWN)


def fmt(value: Any) -> str:
    try:
        return format(_q(_d(value)), "f")
    except (InvalidOperation, TypeError, ValueError):
        return "0.00000000"


def compact(value: Any) -> str:
    return fmt(value).rstrip("0").rstrip(".") or "0"


def _state(db: dict) -> dict:
    if DB_KEY not in db:
        db[DB_KEY] = {
            "schema_version": 2,
            "next_trade_sequence": 1,
            "pool": {
                "credits": fmt(INITIAL_POOL_CREDITS),
                "slh": fmt(INITIAL_POOL_SLH),
            },
            "users": {},
            "trades": [],
        }
    sim = db[DB_KEY]
    if not isinstance(sim, dict) or sim.get("schema_version") != 2:
        raise ValueError("PAPER_SIM_STATE_INVALID")
    if not isinstance(sim.get("pool"), dict) or not isinstance(sim.get("users"), dict):
        raise ValueError("PAPER_SIM_STATE_INVALID")
    if not isinstance(sim.get("trades"), list):
        raise ValueError("PAPER_SIM_STATE_INVALID")
    for field in ("credits", "slh"):
        value = _d(sim["pool"].get(field))
        if value <= ZERO:
            raise ValueError("PAPER_SIM_POOL_INVALID")
    return sim


def _liquidation_quote(sim: dict, slh_amount: Any) -> Decimal:
    """Estimate Demo Credits from selling this Demo-SLH quantity into the current AMM."""
    amount = _q(_d(slh_amount))
    if amount <= ZERO:
        return ZERO
    pool_credits = _d(sim["pool"]["credits"])
    pool_slh = _d(sim["pool"]["slh"])
    fee = _q(amount * FEE_RATE)
    effective_in = amount - fee
    if effective_in <= ZERO:
        return ZERO
    return _q(pool_credits * effective_in / (pool_slh + effective_in))


def _liquidation_value(sim: dict, wallet: dict) -> Decimal:
    """Cash plus conservative immediate AMM liquidation proceeds, after the demo fee."""
    return _d(wallet["credits"]) + _liquidation_quote(sim, wallet["slh"])


def _user(sim: dict, uid: str, now: str) -> dict:
    uid = str(uid or "").strip()
    if not uid.isdigit():
        raise ValueError("PAPER_SIM_UID_INVALID")
    users = sim["users"]
    if uid not in users:
        wallet = {
            "credits": fmt(STARTING_CREDITS),
            "slh": fmt(STARTING_SLH),
        }
        users[uid] = {
            "created_at": now,
            "wallet": wallet,
            "requests": {},
            "reset_count": 0,
        }
        users[uid]["starting_value_credits"] = fmt(_liquidation_value(sim, wallet))
    record = users[uid]
    if not isinstance(record, dict) or not isinstance(record.get("wallet"), dict):
        raise ValueError("PAPER_SIM_USER_STATE_INVALID")
    for field in ("credits", "slh"):
        balance = _d(record["wallet"].get(field))
        if balance < ZERO:
            raise ValueError("PAPER_SIM_BALANCE_INVALID")
    if not isinstance(record.get("requests"), dict):
        raise ValueError("PAPER_SIM_REQUEST_STATE_INVALID")
    return record


def _snapshot(sim: dict, user: dict) -> dict:
    wallet = user["wallet"]
    pool_credits = _d(sim["pool"]["credits"])
    pool_slh = _d(sim["pool"]["slh"])
    price = pool_credits / pool_slh
    credits = _d(wallet["credits"])
    slh = _d(wallet["slh"])
    # Do not report unrealized spot-price inflation as profit. Value the position
    # at estimated proceeds from an immediate full sale into this pool, including
    # the same demo fee and AMM price impact that a real simulator trade would incur.
    equity = _liquidation_value(sim, wallet)
    starting = _d(user.get("starting_value_credits", STARTING_CREDITS + STARTING_SLH))
    return {
        "demo_credits": fmt(credits),
        "demo_slh": fmt(slh),
        "pool_credits": fmt(pool_credits),
        "pool_slh": fmt(pool_slh),
        "price_credits_per_slh": fmt(price),
        "portfolio_value_credits": fmt(equity),
        "change_from_start_credits": fmt(equity - starting),
        "created_at": str(user.get("created_at") or ""),
        "reset_count": int(user.get("reset_count", 0) or 0),
    }


def account_in_db(db: dict, uid: str, now: str | None = None) -> dict:
    sim = _state(db)
    user = _user(sim, str(uid), _now(now))
    return _snapshot(sim, user)


def account(uid: str) -> dict:
    return state_manager.atomic_update(lambda db: account_in_db(db, str(uid)))


def _remember(user: dict, request_id: str, result: dict) -> None:
    requests = user["requests"]
    requests[request_id] = {
        key: value for key, value in result.items()
        if key not in {"account", "duplicate"}
    }
    while len(requests) > MAX_REQUESTS_PER_USER:
        oldest = next(iter(requests))
        requests.pop(oldest, None)


def _cached_result(sim: dict, user: dict, result: dict, duplicate: bool) -> dict:
    return {
        **result,
        "duplicate": duplicate,
        "account": _snapshot(sim, user),
    }


def trade_in_db(
    db: dict,
    uid: str,
    side: str,
    amount: Any,
    request_id: str,
    now: str | None = None,
) -> dict:
    """Execute an atomic paper AMM market order. Buy amount is quote budget;
    sell amount is base quantity. request_id enables replay protection.
    """
    timestamp = _now(now)
    sim = _state(db)
    user = _user(sim, str(uid), timestamp)
    side = str(side or "").strip().lower()
    request_id = str(request_id or "").strip()[:200]
    if not request_id:
        return _cached_result(sim, user, {"status": "BLOCKED", "error": "REQUEST_ID_REQUIRED"}, False)

    prior = user["requests"].get(request_id)
    if isinstance(prior, dict):
        return _cached_result(sim, user, prior, True)

    if side not in {"buy", "sell"}:
        result = {"status": "BLOCKED", "error": "INVALID_SIDE"}
        _remember(user, request_id, result)
        return _cached_result(sim, user, result, False)

    try:
        quantity = _q(_d(amount))
    except (InvalidOperation, TypeError, ValueError):
        result = {"status": "BLOCKED", "error": "INVALID_AMOUNT"}
        _remember(user, request_id, result)
        return _cached_result(sim, user, result, False)
    if quantity < MIN_AMOUNT or quantity > MAX_AMOUNT:
        result = {"status": "BLOCKED", "error": "AMOUNT_OUT_OF_RANGE"}
        _remember(user, request_id, result)
        return _cached_result(sim, user, result, False)

    wallet = user["wallet"]
    pool = sim["pool"]
    pool_credits = _d(pool["credits"])
    pool_slh = _d(pool["slh"])
    price_before = pool_credits / pool_slh
    credits = _d(wallet["credits"])
    slh = _d(wallet["slh"])

    if side == "buy":
        # Amount is the total DEMO-CREDITS budget, fee included.
        if quantity > credits:
            result = {"status": "BLOCKED", "error": "INSUFFICIENT_DEMO_CREDITS"}
            _remember(user, request_id, result)
            return _cached_result(sim, user, result, False)
        fee = _q(quantity * FEE_RATE)
        effective_in = quantity - fee
        slh_out = _q(pool_slh * effective_in / (pool_credits + effective_in))
        if slh_out <= ZERO or slh_out > pool_slh:
            result = {"status": "BLOCKED", "error": "AMOUNT_TOO_SMALL"}
            _remember(user, request_id, result)
            return _cached_result(sim, user, result, False)
        wallet["credits"] = fmt(credits - quantity)
        wallet["slh"] = fmt(slh + slh_out)
        pool["credits"] = fmt(pool_credits + quantity)
        pool["slh"] = fmt(pool_slh - slh_out)
        filled_amount = slh_out
        quote_amount = quantity
        fee_asset = "DEMO-CREDITS"
        average_price = quantity / slh_out
    else:
        # Amount is the total DEMO-SLH quantity to sell; fee is charged in SLH.
        if quantity > slh:
            result = {"status": "BLOCKED", "error": "INSUFFICIENT_DEMO_SLH"}
            _remember(user, request_id, result)
            return _cached_result(sim, user, result, False)
        fee = _q(quantity * FEE_RATE)
        effective_in = quantity - fee
        credits_out = _q(pool_credits * effective_in / (pool_slh + effective_in))
        if credits_out <= ZERO or credits_out > pool_credits:
            result = {"status": "BLOCKED", "error": "AMOUNT_TOO_SMALL"}
            _remember(user, request_id, result)
            return _cached_result(sim, user, result, False)
        wallet["slh"] = fmt(slh - quantity)
        wallet["credits"] = fmt(credits + credits_out)
        pool["slh"] = fmt(pool_slh + quantity)
        pool["credits"] = fmt(pool_credits - credits_out)
        filled_amount = quantity
        quote_amount = credits_out
        fee_asset = "DEMO-SLH"
        average_price = credits_out / quantity

    price_after = _d(pool["credits"]) / _d(pool["slh"])
    if side == "buy":
        impact = max(ZERO, (average_price / price_before - Decimal("1")) * Decimal("100"))
    else:
        impact = max(ZERO, (Decimal("1") - average_price / price_before) * Decimal("100"))

    sequence = int(sim.get("next_trade_sequence", 1) or 1)
    if sequence < 1:
        raise ValueError("PAPER_SIM_SEQUENCE_INVALID")
    sim["next_trade_sequence"] = sequence + 1
    trade = {
        "id": f"PSIM-{sequence:08d}",
        "uid": str(uid),
        "side": side,
        "asset_pair": "DEMO-SLH/DEMO-CREDITS",
        "amount_slh": fmt(filled_amount),
        "amount_credits": fmt(quote_amount),
        "average_price_credits_per_slh": fmt(average_price),
        "fee_amount": fmt(fee),
        "fee_asset": fee_asset,
        "price_before": fmt(price_before),
        "price_after": fmt(price_after),
        "price_impact_pct": fmt(impact),
        "created_at": timestamp,
        "request_id": request_id,
    }
    sim["trades"].append(trade)
    if len(sim["trades"]) > MAX_TRADES:
        del sim["trades"][:-MAX_TRADES]

    result = {"status": "FILLED", "trade": trade}
    _remember(user, request_id, result)
    return _cached_result(sim, user, result, False)


def trade(uid: str, side: str, amount: Any, request_id: str) -> dict:
    return state_manager.atomic_update(
        lambda db: trade_in_db(db, str(uid), side, amount, request_id)
    )


def history_in_db(db: dict, uid: str, limit: int = 10) -> list[dict]:
    sim = db.get(DB_KEY)
    if not isinstance(sim, dict) or not isinstance(sim.get("trades"), list):
        return []
    try:
        count = max(1, min(50, int(limit)))
    except (TypeError, ValueError):
        count = 10
    rows = [
        row for row in sim["trades"]
        if isinstance(row, dict) and str(row.get("uid")) == str(uid)
    ]
    return list(reversed(rows[-count:]))


def history(uid: str, limit: int = 10) -> list[dict]:
    return history_in_db(state_manager.load_db(), str(uid), limit)


def leaderboard_in_db(db: dict, limit: int = 10) -> list[dict]:
    sim = db.get(DB_KEY)
    if not isinstance(sim, dict) or not isinstance(sim.get("users"), dict):
        return []
    try:
        count = max(1, min(50, int(limit)))
    except (TypeError, ValueError):
        count = 10
    pool = sim.get("pool") or {}
    try:
        _d(pool["credits"])
        _d(pool["slh"])
        if _d(pool["credits"]) <= ZERO or _d(pool["slh"]) <= ZERO:
            return []
    except (KeyError, InvalidOperation, TypeError, ValueError):
        return []
    ranked = []
    for uid, user in sim["users"].items():
        try:
            wallet = user["wallet"]
            value = _liquidation_value(sim, wallet)
            starting = _d(user.get("starting_value_credits", STARTING_CREDITS + STARTING_SLH))
        except (KeyError, InvalidOperation, TypeError, ValueError):
            continue
        # Stable pseudonym; Telegram IDs and user profile data never appear here.
        alias = hashlib.sha256(str(uid).encode("utf-8")).hexdigest()[:6].upper()
        ranked.append({
            "alias": f"Trader-{alias}",
            "portfolio_value_credits": fmt(value),
            "change_from_start_credits": fmt(value - starting),
            "reset_count": int(user.get("reset_count", 0) or 0),
        })
    ranked.sort(key=lambda row: _d(row["portfolio_value_credits"]), reverse=True)
    return ranked[:count]


def leaderboard(limit: int = 10) -> list[dict]:
    return leaderboard_in_db(state_manager.load_db(), limit)


def audit_in_db(db: dict) -> dict:
    """Verify the demo namespace is coherent without touching it."""
    sim = db.get(DB_KEY)
    if sim is None:
        return {"status": "EMPTY", "users": 0, "trades": 0, "real_wallets_touched": False, "canonical_ledger_touched": False}
    if not isinstance(sim, dict):
        return {"status": "BLOCKED", "reason": "PAPER_SIM_STATE_INVALID", "real_wallets_touched": False, "canonical_ledger_touched": False}
    errors = []
    if sim.get("schema_version") != 2:
        errors.append("unsupported_schema_version")
    pool = sim.get("pool")
    users = sim.get("users")
    trades = sim.get("trades")
    if not isinstance(pool, dict) or not isinstance(users, dict) or not isinstance(trades, list):
        return {"status": "BLOCKED", "reason": "PAPER_SIM_STATE_INVALID", "real_wallets_touched": False, "canonical_ledger_touched": False}
    for field in ("credits", "slh"):
        try:
            if _d(pool[field]) <= ZERO:
                errors.append(f"pool_{field}_not_positive")
        except (KeyError, InvalidOperation, TypeError, ValueError):
            errors.append(f"pool_{field}_invalid")
    for uid, user in users.items():
        try:
            if not str(uid).isdigit():
                errors.append("invalid_demo_uid")
            if not isinstance(user, dict) or not isinstance(user.get("wallet"), dict):
                errors.append("invalid_demo_user")
                continue
            wallet = user["wallet"]
            if _d(wallet["credits"]) < ZERO or _d(wallet["slh"]) < ZERO:
                errors.append("negative_demo_balance")
            if not isinstance(user.get("requests"), dict):
                errors.append("invalid_request_cache")
        except (KeyError, InvalidOperation, TypeError, ValueError):
            errors.append("invalid_demo_balance")
    try:
        next_sequence = int(sim.get("next_trade_sequence"))
        if next_sequence < 1:
            errors.append("invalid_next_trade_sequence")
    except (TypeError, ValueError, OverflowError):
        next_sequence = 0
        errors.append("invalid_next_trade_sequence")

    seen = set()
    max_sequence = 0
    required_trade_fields = (
        "uid", "side", "amount_slh", "amount_credits",
        "average_price_credits_per_slh", "fee_amount", "price_before",
        "price_after", "price_impact_pct", "created_at", "request_id",
    )
    for row in trades:
        if not isinstance(row, dict) or not row.get("id"):
            errors.append("invalid_trade_record")
            continue
        trade_id = str(row["id"])
        if trade_id in seen:
            errors.append("duplicate_trade_id")
        seen.add(trade_id)
        if not trade_id.startswith("PSIM-"):
            errors.append("invalid_trade_id_format")
        else:
            try:
                max_sequence = max(max_sequence, int(trade_id.split("-", 1)[1]))
            except (TypeError, ValueError, OverflowError):
                errors.append("invalid_trade_id_format")
        missing = [field for field in required_trade_fields if field not in row]
        if missing:
            errors.append("incomplete_trade_record")
            continue
        if str(row.get("uid")) not in users:
            errors.append("trade_user_missing")
        if row.get("side") not in {"buy", "sell"}:
            errors.append("invalid_trade_side")
        if not str(row.get("request_id") or "").strip():
            errors.append("trade_request_id_missing")
        try:
            if any(_d(row[field]) <= ZERO for field in (
                "amount_slh", "amount_credits", "average_price_credits_per_slh",
                "price_before", "price_after",
            )):
                errors.append("non_positive_trade_value")
            if _d(row["fee_amount"]) < ZERO or _d(row["price_impact_pct"]) < ZERO:
                errors.append("negative_trade_fee_or_impact")
        except (InvalidOperation, TypeError, ValueError):
            errors.append("invalid_trade_numeric_field")
    if next_sequence and max_sequence >= next_sequence:
        errors.append("trade_sequence_ahead_of_counter")
    return {
        "status": "PASS" if not errors else "BLOCKED",
        "users": len(users),
        "trades": len(trades),
        "finding_count": len(errors),
        "findings": errors[:25],
        "real_wallets_touched": False,
        "canonical_ledger_touched": False,
    }


def audit() -> dict:
    return audit_in_db(state_manager.load_db())
