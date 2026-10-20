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
MIN_LIMIT_PRICE = Decimal('0.00000001')
MAX_LIMIT_PRICE = Decimal('1000000')
MAX_OPEN_LIMIT_ORDERS_PER_USER = 100
MAX_PAPER_ORDERS = 10000


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
            "schema_version": 3,
            "next_trade_sequence": 1,
            "next_order_sequence": 1,
            "pool": {
                "credits": fmt(INITIAL_POOL_CREDITS),
                "slh": fmt(INITIAL_POOL_SLH),
            },
            "users": {},
            "trades": [],
            "orders": [],
        }
    sim = db[DB_KEY]
    if not isinstance(sim, dict):
        raise ValueError("PAPER_SIM_STATE_INVALID")
    # Additive-only migration: preserve every existing virtual balance, pool
    # reserve, trade and replay cache from v2. Never reset unknown/corrupt state.
    if sim.get("schema_version") == 2:
        if (
            not isinstance(sim.get("pool"), dict)
            or not isinstance(sim.get("users"), dict)
            or not isinstance(sim.get("trades"), list)
        ):
            raise ValueError("PAPER_SIM_STATE_INVALID")
        sim.setdefault("orders", [])
        sim.setdefault("next_order_sequence", 1)
        for _uid, _record in sim["users"].items():
            if isinstance(_record, dict):
                _record.setdefault("_uid", str(_uid))
        sim["schema_version"] = 3
    if sim.get("schema_version") != 3:
        raise ValueError("PAPER_SIM_STATE_INVALID")
    if not isinstance(sim.get("pool"), dict) or not isinstance(sim.get("users"), dict):
        raise ValueError("PAPER_SIM_STATE_INVALID")
    if not isinstance(sim.get("trades"), list) or not isinstance(sim.get("orders"), list):
        raise ValueError("PAPER_SIM_STATE_INVALID")
    for field in ("credits", "slh"):
        value = _d(sim["pool"].get(field))
        if value <= ZERO:
            raise ValueError("PAPER_SIM_POOL_INVALID")
    try:
        if int(sim.get("next_trade_sequence", 0)) < 1 or int(sim.get("next_order_sequence", 0)) < 1:
            raise ValueError
    except (TypeError, ValueError, OverflowError):
        raise ValueError("PAPER_SIM_SEQUENCE_INVALID")
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
            "_uid": uid,
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


def _reserved_balances(sim: dict, uid: str) -> tuple[Decimal, Decimal]:
    reserved_credits = ZERO
    reserved_slh = ZERO
    for order in sim.get("orders", []):
        if not isinstance(order, dict):
            continue
        if str(order.get("uid")) != str(uid):
            continue
        if order.get("status") not in {"OPEN", "REVIEW_REQUIRED"}:
            continue
        reserved_credits += _d(order.get("reserved_credits", 0))
        reserved_slh += _d(order.get("reserved_slh", 0))
    return _q(reserved_credits), _q(reserved_slh)


def _snapshot(sim: dict, user: dict, uid: str) -> dict:
    wallet = user["wallet"]
    pool_credits = _d(sim["pool"]["credits"])
    pool_slh = _d(sim["pool"]["slh"])
    price = pool_credits / pool_slh
    credits = _d(wallet["credits"])
    slh = _d(wallet["slh"])
    reserved_credits, reserved_slh = _reserved_balances(sim, uid)
    # Include assets locked by open limit orders in portfolio value, but keep
    # "available" balances separate so they cannot be spent twice.
    total_wallet = {
        "credits": fmt(credits + reserved_credits),
        "slh": fmt(slh + reserved_slh),
    }
    equity = _liquidation_value(sim, total_wallet)
    starting = _d(user.get("starting_value_credits", STARTING_CREDITS + STARTING_SLH))
    return {
        "demo_credits": fmt(credits),
        "demo_slh": fmt(slh),
        "reserved_demo_credits": fmt(reserved_credits),
        "reserved_demo_slh": fmt(reserved_slh),
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
    return _snapshot(sim, user, str(uid))


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
        "account": _snapshot(sim, user, str(user.get("_uid") or "")),
    }


def _limit_preview(sim: dict, side: str, amount: Decimal) -> dict:
    pool_credits = _d(sim["pool"]["credits"])
    pool_slh = _d(sim["pool"]["slh"])
    fee = _q(amount * FEE_RATE)
    effective_in = amount - fee
    if effective_in <= ZERO:
        raise ValueError("AMOUNT_TOO_SMALL")
    if side == "buy":
        slh_out = _q(pool_slh * effective_in / (pool_credits + effective_in))
        if slh_out <= ZERO:
            raise ValueError("AMOUNT_TOO_SMALL")
        return {
            "amount_slh": slh_out,
            "amount_credits": amount,
            "average_price": amount / slh_out,
            "fee": fee,
            "fee_asset": "DEMO-CREDITS",
        }
    credits_out = _q(pool_credits * effective_in / (pool_slh + effective_in))
    if credits_out <= ZERO:
        raise ValueError("AMOUNT_TOO_SMALL")
    return {
        "amount_slh": amount,
        "amount_credits": credits_out,
        "average_price": credits_out / amount,
        "fee": fee,
        "fee_asset": "DEMO-SLH",
    }


def _match_limit_orders(sim: dict, timestamp: str) -> list[dict]:
    """Match crossed orders FIFO; the execution average must satisfy its limit."""
    orders = sim["orders"]
    fills = []
    # A successful fill changes the pool price. Iterate again so earlier FIFO
    # orders re-check their limit after later fills move the pool.
    max_passes = min(len(orders) + 1, MAX_PAPER_ORDERS + 1)
    for _ in range(max_passes):
        made_progress = False
        for order in sorted(
            [row for row in orders if isinstance(row, dict) and row.get("status") == "OPEN"],
            key=lambda row: int(row.get("sequence", 0) or 0),
        ):
            side = str(order.get("side") or "")
            uid = str(order.get("uid") or "")
            if side not in {"buy", "sell"}:
                order["status"] = "REVIEW_REQUIRED"
                order["last_error"] = "INVALID_ORDER_SIDE"
                continue
            pool_price = _d(sim["pool"]["credits"]) / _d(sim["pool"]["slh"])
            limit_price = _d(order["limit_price"])
            if (side == "buy" and pool_price > limit_price) or (
                side == "sell" and pool_price < limit_price
            ):
                continue

            reserved_field = "reserved_credits" if side == "buy" else "reserved_slh"
            wallet_field = "credits" if side == "buy" else "slh"
            amount = _d(order.get(reserved_field, 0))
            if amount <= ZERO:
                order["status"] = "REVIEW_REQUIRED"
                order["last_error"] = "MISSING_RESERVED_AMOUNT"
                continue
            user = sim["users"].get(uid)
            if not isinstance(user, dict) or not isinstance(user.get("wallet"), dict):
                order["status"] = "REVIEW_REQUIRED"
                order["last_error"] = "ORDER_USER_MISSING"
                continue
            fill_request_id = f"paper-limit-fill:{order.get('id')}"
            if fill_request_id in user.get("requests", {}):
                # A filled-request cache without a terminal order state signals
                # inconsistent state. Never debit/release twice.
                order["status"] = "REVIEW_REQUIRED"
                order["last_error"] = "FILL_REQUEST_ALREADY_EXISTS"
                continue
            try:
                preview = _limit_preview(sim, side, amount)
            except (InvalidOperation, TypeError, ValueError):
                order["status"] = "REVIEW_REQUIRED"
                order["last_error"] = "ORDER_PREVIEW_INVALID"
                continue
            avg_price = preview["average_price"]
            if side == "buy" and avg_price > limit_price:
                continue
            if side == "sell" and avg_price < limit_price:
                continue

            wallet = user["wallet"]
            original_balance = _d(wallet.get(wallet_field, 0))
            # Unlock into the spendable wallet just for the canonical simulator
            # trade call. The whole operation is within the same atomic DB update.
            wallet[wallet_field] = fmt(original_balance + amount)
            result = trade_in_db(
                sim_to_db(sim), uid, side, amount, fill_request_id,
                now=timestamp, _process_limits=False,
            )
            if result.get("status") != "FILLED":
                wallet[wallet_field] = fmt(original_balance)
                user.get("requests", {}).pop(fill_request_id, None)
                order["status"] = "REVIEW_REQUIRED"
                order["last_error"] = str(result.get("error") or "LIMIT_FILL_BLOCKED")
                order["updated_at"] = timestamp
                continue

            trade_row = result["trade"]
            order["status"] = "FILLED"
            order["reserved_credits"] = "0.00000000"
            order["reserved_slh"] = "0.00000000"
            order["filled_at"] = timestamp
            order["filled_trade_id"] = trade_row["id"]
            order["updated_at"] = timestamp
            order.pop("last_error", None)
            fills.append({
                "order_id": order["id"],
                "trade_id": trade_row["id"],
                "side": side,
                "amount_slh": trade_row["amount_slh"],
                "amount_credits": trade_row["amount_credits"],
                "average_price_credits_per_slh": trade_row["average_price_credits_per_slh"],
            })
            made_progress = True
        if not made_progress:
            break
    return fills


def sim_to_db(sim: dict) -> dict:
    """Provide the state root expected by trade_in_db without copying the simulator."""
    # The caller is operating inside state_manager.atomic_update already.
    # This deliberately wraps the same mutable simulator object for a nested call.
    return {"paper_simulation": sim, "users": {}, "ledger": []}


def trade_in_db(
    db: dict,
    uid: str,
    side: str,
    amount: Any,
    request_id: str,
    now: str | None = None,
    *,
    _process_limits: bool = True,
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
    if _process_limits:
        result["limit_fills"] = _match_limit_orders(sim, timestamp)
    _remember(user, request_id, result)
    return _cached_result(sim, user, result, False)


def trade(uid: str, side: str, amount: Any, request_id: str) -> dict:
    return state_manager.atomic_update(
        lambda db: trade_in_db(db, str(uid), side, amount, request_id)
    )


def limit_order_in_db(
    db: dict,
    uid: str,
    side: str,
    amount: Any,
    limit_price: Any,
    request_id: str,
    now: str | None = None,
) -> dict:
    """Reserve a virtual balance and place a one-shot AMM limit order."""
    timestamp = _now(now)
    sim = _state(db)
    uid = str(uid)
    user = _user(sim, uid, timestamp)
    side = str(side or "").strip().lower()
    request_id = str(request_id or "").strip()[:200]
    if not request_id:
        return _cached_result(sim, user, {"status": "BLOCKED", "error": "REQUEST_ID_REQUIRED"}, False)
    if side not in {"buy", "sell"}:
        return _cached_result(sim, user, {"status": "BLOCKED", "error": "INVALID_SIDE"}, False)

    prior = user["requests"].get(request_id)
    if isinstance(prior, dict) and prior.get("order_id"):
        old = next(
            (row for row in sim["orders"] if isinstance(row, dict) and row.get("id") == prior["order_id"]),
            None,
        )
        if old:
            return _cached_result(sim, user, {"status": "DUPLICATE_REQUEST", "order": dict(old)}, True)
        return _cached_result(sim, user, {"status": "BLOCKED", "error": "ORDER_REQUEST_REFERENCE_MISSING"}, True)
    if prior:
        return _cached_result(sim, user, {"status": "DUPLICATE_REQUEST"}, True)

    try:
        quantity = _q(_d(amount))
    except (InvalidOperation, TypeError, ValueError):
        return _cached_result(sim, user, {"status": "BLOCKED", "error": "INVALID_AMOUNT"}, False)
    try:
        price = _q(_d(limit_price))
    except (InvalidOperation, TypeError, ValueError):
        return _cached_result(sim, user, {"status": "BLOCKED", "error": "INVALID_LIMIT_PRICE"}, False)
    if quantity < MIN_AMOUNT or quantity > MAX_AMOUNT:
        return _cached_result(sim, user, {"status": "BLOCKED", "error": "AMOUNT_OUT_OF_RANGE"}, False)
    if price < MIN_LIMIT_PRICE or price > MAX_LIMIT_PRICE:
        return _cached_result(sim, user, {"status": "BLOCKED", "error": "LIMIT_PRICE_OUT_OF_RANGE"}, False)
    active = [
        row for row in sim["orders"]
        if isinstance(row, dict)
        and str(row.get("uid")) == uid
        and row.get("status") in {"OPEN", "REVIEW_REQUIRED"}
    ]
    if len(active) >= MAX_OPEN_LIMIT_ORDERS_PER_USER:
        return _cached_result(sim, user, {"status": "BLOCKED", "error": "TOO_MANY_OPEN_ORDERS"}, False)
    if len(sim["orders"]) >= MAX_PAPER_ORDERS:
        return _cached_result(sim, user, {"status": "BLOCKED", "error": "ORDER_HISTORY_FULL"}, False)

    wallet = user["wallet"]
    reserved_credits = ZERO
    reserved_slh = ZERO
    if side == "buy":
        if quantity > _d(wallet["credits"]):
            return _cached_result(sim, user, {"status": "BLOCKED", "error": "INSUFFICIENT_DEMO_CREDITS"}, False)
        wallet["credits"] = fmt(_d(wallet["credits"]) - quantity)
        reserved_credits = quantity
    else:
        if quantity > _d(wallet["slh"]):
            return _cached_result(sim, user, {"status": "BLOCKED", "error": "INSUFFICIENT_DEMO_SLH"}, False)
        wallet["slh"] = fmt(_d(wallet["slh"]) - quantity)
        reserved_slh = quantity

    sequence = int(sim["next_order_sequence"])
    sim["next_order_sequence"] = sequence + 1
    order = {
        "id": f"PSIM-O{sequence:08d}",
        "sequence": sequence,
        "uid": uid,
        "side": side,
        "order_type": "limit",
        "asset_pair": "DEMO-SLH/DEMO-CREDITS",
        "original_amount": fmt(quantity),
        "limit_price": fmt(price),
        "reserved_credits": fmt(reserved_credits),
        "reserved_slh": fmt(reserved_slh),
        "status": "OPEN",
        "created_at": timestamp,
        "updated_at": timestamp,
        "request_id": request_id,
    }
    sim["orders"].append(order)
    _match_limit_orders(sim, timestamp)
    status = str(order.get("status") or "OPEN")
    result = {"status": status, "order": dict(order)}
    _remember(user, request_id, {"status": "ORDER_ACCEPTED", "order_id": order["id"]})
    return _cached_result(sim, user, result, False)


def limit_order(uid: str, side: str, amount: Any, limit_price: Any, request_id: str) -> dict:
    return state_manager.atomic_update(
        lambda db: limit_order_in_db(db, str(uid), side, amount, limit_price, request_id)
    )


def cancel_order_in_db(
    db: dict, uid: str, order_id: str, request_id: str, now: str | None = None
) -> dict:
    timestamp = _now(now)
    sim = _state(db)
    uid = str(uid)
    user = _user(sim, uid, timestamp)
    order_id = str(order_id or "").strip()
    request_id = str(request_id or "").strip()[:200]
    if not order_id or not request_id:
        return _cached_result(sim, user, {"status": "BLOCKED", "error": "INVALID_CANCEL_REQUEST"}, False)
    prior = user["requests"].get(request_id)
    if isinstance(prior, dict):
        return _cached_result(sim, user, prior, True)
    order = next(
        (row for row in sim["orders"] if isinstance(row, dict) and row.get("id") == order_id),
        None,
    )
    if not order or str(order.get("uid")) != uid:
        result = {"status": "BLOCKED", "error": "ORDER_NOT_FOUND"}
        _remember(user, request_id, result)
        return _cached_result(sim, user, result, False)
    if order.get("status") == "CANCELLED":
        result = {"status": "ALREADY_CANCELLED", "order": dict(order)}
        _remember(user, request_id, result)
        return _cached_result(sim, user, result, False)
    if order.get("status") not in {"OPEN", "REVIEW_REQUIRED"}:
        result = {"status": "BLOCKED", "error": "ORDER_NOT_CANCELLABLE", "order": dict(order)}
        _remember(user, request_id, result)
        return _cached_result(sim, user, result, False)

    wallet = user["wallet"]
    wallet["credits"] = fmt(_d(wallet["credits"]) + _d(order.get("reserved_credits", 0)))
    wallet["slh"] = fmt(_d(wallet["slh"]) + _d(order.get("reserved_slh", 0)))
    order["reserved_credits"] = "0.00000000"
    order["reserved_slh"] = "0.00000000"
    order["status"] = "CANCELLED"
    order["cancelled_at"] = timestamp
    order["updated_at"] = timestamp
    order.pop("last_error", None)
    result = {"status": "CANCELLED", "order": dict(order)}
    _remember(user, request_id, result)
    return _cached_result(sim, user, result, False)


def cancel_order(uid: str, order_id: str, request_id: str) -> dict:
    return state_manager.atomic_update(
        lambda db: cancel_order_in_db(db, str(uid), order_id, request_id)
    )


def orders_in_db(db: dict, uid: str, limit: int = 20) -> list[dict]:
    sim = db.get(DB_KEY)
    if not isinstance(sim, dict) or not isinstance(sim.get("orders"), list):
        return []
    try:
        count = max(1, min(50, int(limit)))
    except (TypeError, ValueError):
        count = 20
    rows = [
        row for row in sim["orders"]
        if isinstance(row, dict) and str(row.get("uid")) == str(uid)
    ]
    return [dict(row) for row in reversed(rows[-count:])]


def orders(uid: str, limit: int = 20) -> list[dict]:
    return orders_in_db(state_manager.load_db(), str(uid), limit)


def match_pending_orders_in_db(db: dict, now: str | None = None) -> dict:
    sim = _state(db)
    fills = _match_limit_orders(sim, _now(now))
    return {
        "status": "PASS",
        "fills": fills,
        "open_orders": sum(1 for row in sim["orders"] if isinstance(row, dict) and row.get("status") == "OPEN"),
    }


def match_pending_orders() -> dict:
    return state_manager.atomic_update(match_pending_orders_in_db)


def _order_view(order: dict) -> dict:
    return {
        "id": str(order.get("id") or ""),
        "side": str(order.get("side") or ""),
        "limit_price": str(order.get("limit_price") or "0"),
        "amount": str(order.get("amount") or "0"),
        "status": str(order.get("status") or "UNKNOWN"),
        "reserved_credits": str(order.get("reserved_credits") or "0"),
        "reserved_slh": str(order.get("reserved_slh") or "0"),
        "created_at": str(order.get("created_at") or ""),
        "updated_at": str(order.get("updated_at") or ""),
        "filled_at": str(order.get("filled_at") or ""),
        "filled_trade_id": str(order.get("filled_trade_id") or ""),
        "cancelled_at": str(order.get("cancelled_at") or ""),
        "last_error": str(order.get("last_error") or ""),
    }


def place_limit_in_db(
    db: dict,
    uid: str,
    side: str,
    limit_price: Any,
    amount: Any,
    request_id: str,
    now: str | None = None,
) -> dict:
    """Place a fully reserved, all-or-none simulated limit order."""
    timestamp = _now(now)
    uid = str(uid)
    sim = _state(db)
    user = _user(sim, uid, timestamp)
    request_id = str(request_id or "").strip()[:200]
    if not request_id:
        return _cached_result(sim, user, {"status": "BLOCKED", "error": "REQUEST_ID_REQUIRED"}, False)

    prior = user["requests"].get(request_id)
    if isinstance(prior, dict):
        replay = dict(prior)
        saved_order = prior.get("order")
        if isinstance(saved_order, dict) and saved_order.get("id"):
            current = next(
                (row for row in sim["orders"] if isinstance(row, dict) and row.get("id") == saved_order["id"]),
                None,
            )
            if current:
                replay["order"] = _order_view(current)
        return _cached_result(sim, user, replay, True)

    side = str(side or "").strip().lower()
    if side not in {"buy", "sell"}:
        result = {"status": "BLOCKED", "error": "INVALID_SIDE"}
        _remember(user, request_id, result)
        return _cached_result(sim, user, result, False)

    try:
        price = _q(_d(limit_price))
        quantity = _q(_d(amount))
    except (InvalidOperation, TypeError, ValueError):
        result = {"status": "BLOCKED", "error": "INVALID_PRICE_OR_AMOUNT"}
        _remember(user, request_id, result)
        return _cached_result(sim, user, result, False)
    if price < MIN_LIMIT_PRICE or price > MAX_LIMIT_PRICE:
        result = {"status": "BLOCKED", "error": "LIMIT_PRICE_OUT_OF_RANGE"}
        _remember(user, request_id, result)
        return _cached_result(sim, user, result, False)
    if quantity < MIN_AMOUNT or quantity > MAX_AMOUNT:
        result = {"status": "BLOCKED", "error": "AMOUNT_OUT_OF_RANGE"}
        _remember(user, request_id, result)
        return _cached_result(sim, user, result, False)

    active_for_user = sum(
        1 for row in sim["orders"]
        if isinstance(row, dict)
        and str(row.get("uid")) == uid
        and row.get("status") in {"OPEN", "REVIEW_REQUIRED"}
    )
    if active_for_user >= MAX_OPEN_LIMIT_ORDERS_PER_USER or len(sim["orders"]) >= MAX_PAPER_ORDERS:
        result = {"status": "BLOCKED", "error": "LIMIT_ORDER_CAP_REACHED"}
        _remember(user, request_id, result)
        return _cached_result(sim, user, result, False)

    wallet = user["wallet"]
    if side == "buy":
        if quantity > _d(wallet.get("credits", 0)):
            result = {"status": "BLOCKED", "error": "INSUFFICIENT_DEMO_CREDITS"}
            _remember(user, request_id, result)
            return _cached_result(sim, user, result, False)
        reserved_credits, reserved_slh = quantity, ZERO
        wallet["credits"] = fmt(_d(wallet["credits"]) - quantity)
    else:
        if quantity > _d(wallet.get("slh", 0)):
            result = {"status": "BLOCKED", "error": "INSUFFICIENT_DEMO_SLH"}
            _remember(user, request_id, result)
            return _cached_result(sim, user, result, False)
        reserved_credits, reserved_slh = ZERO, quantity
        wallet["slh"] = fmt(_d(wallet["slh"]) - quantity)

    try:
        sequence = int(sim.get("next_order_sequence", 1))
    except (TypeError, ValueError, OverflowError):
        raise ValueError("PAPER_SIM_ORDER_SEQUENCE_INVALID")
    if sequence < 1:
        raise ValueError("PAPER_SIM_ORDER_SEQUENCE_INVALID")
    sim["next_order_sequence"] = sequence + 1
    order = {
        "id": f"PLIM-{sequence:08d}",
        "sequence": sequence,
        "uid": uid,
        "side": side,
        "limit_price": fmt(price),
        "amount": fmt(quantity),
        "reserved_credits": fmt(reserved_credits),
        "reserved_slh": fmt(reserved_slh),
        "status": "OPEN",
        "created_at": timestamp,
        "updated_at": timestamp,
        "request_id": request_id,
    }
    sim["orders"].append(order)
    fills = _match_limit_orders(sim, timestamp)
    result = {
        "status": "ORDER_FILLED" if order["status"] == "FILLED" else (
            "ORDER_REVIEW_REQUIRED" if order["status"] == "REVIEW_REQUIRED" else "ORDER_PLACED"
        ),
        "order": _order_view(order),
        "limit_fills": fills,
    }
    _remember(user, request_id, result)
    return _cached_result(sim, user, result, False)


def place_limit(uid: str, side: str, limit_price: Any, amount: Any, request_id: str) -> dict:
    return state_manager.atomic_update(
        lambda db: place_limit_in_db(db, str(uid), side, limit_price, amount, request_id)
    )


def cancel_order_in_db(
    db: dict,
    uid: str,
    order_id: str,
    request_id: str,
    now: str | None = None,
) -> dict:
    timestamp = _now(now)
    uid = str(uid)
    sim = _state(db)
    user = _user(sim, uid, timestamp)
    request_id = str(request_id or "").strip()[:200]
    if not request_id:
        return _cached_result(sim, user, {"status": "BLOCKED", "error": "REQUEST_ID_REQUIRED"}, False)

    prior = user["requests"].get(request_id)
    if isinstance(prior, dict):
        return _cached_result(sim, user, prior, True)

    order_id = str(order_id or "").strip()[:64]
    order = next(
        (row for row in sim["orders"] if isinstance(row, dict)
         and str(row.get("id")) == order_id and str(row.get("uid")) == uid),
        None,
    )
    if order is None:
        result = {"status": "BLOCKED", "error": "ORDER_NOT_FOUND"}
        _remember(user, request_id, result)
        return _cached_result(sim, user, result, False)

    if order.get("status") == "CANCELLED":
        result = {"status": "ALREADY_CANCELLED", "order": _order_view(order)}
        _remember(user, request_id, result)
        return _cached_result(sim, user, result, False)
    if order.get("status") == "FILLED":
        result = {"status": "ALREADY_FILLED", "order": _order_view(order)}
        _remember(user, request_id, result)
        return _cached_result(sim, user, result, False)
    if order.get("status") not in {"OPEN", "REVIEW_REQUIRED"}:
        result = {"status": "BLOCKED", "error": "ORDER_STATE_INVALID"}
        _remember(user, request_id, result)
        return _cached_result(sim, user, result, False)

    try:
        reserved_credits = _d(order.get("reserved_credits", 0))
        reserved_slh = _d(order.get("reserved_slh", 0))
        original_amount = _d(order.get("amount", 0))
    except (InvalidOperation, TypeError, ValueError):
        order["status"] = "REVIEW_REQUIRED"
        order["last_error"] = "RESERVATION_INVALID"
        result = {"status": "BLOCKED", "error": "ORDER_RESERVATION_INVALID"}
        _remember(user, request_id, result)
        return _cached_result(sim, user, result, False)

    if (
        (order.get("side") == "buy" and (reserved_credits != original_amount or reserved_slh != ZERO))
        or (order.get("side") == "sell" and (reserved_slh != original_amount or reserved_credits != ZERO))
        or order.get("side") not in {"buy", "sell"}
    ):
        order["status"] = "REVIEW_REQUIRED"
        order["last_error"] = "RESERVATION_MISMATCH"
        result = {"status": "BLOCKED", "error": "ORDER_RESERVATION_MISMATCH"}
        _remember(user, request_id, result)
        return _cached_result(sim, user, result, False)

    wallet = user["wallet"]
    wallet["credits"] = fmt(_d(wallet.get("credits", 0)) + reserved_credits)
    wallet["slh"] = fmt(_d(wallet.get("slh", 0)) + reserved_slh)
    order["reserved_credits"] = "0.00000000"
    order["reserved_slh"] = "0.00000000"
    order["status"] = "CANCELLED"
    order["cancelled_at"] = timestamp
    order["updated_at"] = timestamp
    order.pop("last_error", None)
    result = {"status": "CANCELLED", "order": _order_view(order)}
    _remember(user, request_id, result)
    return _cached_result(sim, user, result, False)


def cancel_order(uid: str, order_id: str, request_id: str) -> dict:
    return state_manager.atomic_update(
        lambda db: cancel_order_in_db(db, str(uid), order_id, request_id)
    )


def orders_in_db(db: dict, uid: str, limit: int = 20) -> list[dict]:
    sim = db.get(DB_KEY)
    if not isinstance(sim, dict) or not isinstance(sim.get("orders"), list):
        return []
    try:
        count = max(1, min(50, int(limit)))
    except (TypeError, ValueError):
        count = 20
    rows = [
        row for row in sim["orders"]
        if isinstance(row, dict) and str(row.get("uid")) == str(uid)
    ]
    return [_order_view(row) for row in reversed(rows[-count:])]


def orders(uid: str, limit: int = 20) -> list[dict]:
    return orders_in_db(state_manager.load_db(), str(uid), limit)


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
    if sim.get("schema_version") != 3:
        errors.append("unsupported_schema_version")
    pool = sim.get("pool")
    users = sim.get("users")
    trades = sim.get("trades")
    orders = sim.get("orders")
    if not isinstance(pool, dict) or not isinstance(users, dict) or not isinstance(trades, list) or not isinstance(orders, list):
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
    try:
        next_order_sequence = int(sim.get("next_order_sequence"))
        if next_order_sequence < 1:
            errors.append("invalid_next_order_sequence")
    except (TypeError, ValueError, OverflowError):
        next_order_sequence = 0
        errors.append("invalid_next_order_sequence")

    seen_orders = set()
    max_order_sequence = 0
    valid_order_statuses = {"OPEN", "REVIEW_REQUIRED", "FILLED", "CANCELLED"}
    for order in orders:
        if not isinstance(order, dict) or not order.get("id"):
            errors.append("invalid_limit_order_record")
            continue
        order_id = str(order["id"])
        if order_id in seen_orders:
            errors.append("duplicate_limit_order_id")
        seen_orders.add(order_id)
        if not order_id.startswith("PLIM-"):
            errors.append("invalid_limit_order_id_format")
        else:
            try:
                max_order_sequence = max(max_order_sequence, int(order_id.split("-", 1)[1]))
            except (TypeError, ValueError, OverflowError):
                errors.append("invalid_limit_order_id_format")
        side = order.get("side")
        status = order.get("status")
        if side not in {"buy", "sell"}:
            errors.append("invalid_limit_order_side")
        if status not in valid_order_statuses:
            errors.append("invalid_limit_order_status")
        if str(order.get("uid")) not in users:
            errors.append("limit_order_user_missing")
        try:
            price = _d(order["limit_price"])
            amount = _d(order["amount"])
            reserved_credits = _d(order.get("reserved_credits", 0))
            reserved_slh = _d(order.get("reserved_slh", 0))
            if price <= ZERO or amount < MIN_AMOUNT:
                errors.append("invalid_limit_order_price_or_amount")
            if reserved_credits < ZERO or reserved_slh < ZERO:
                errors.append("negative_limit_order_reservation")
            if status in {"OPEN", "REVIEW_REQUIRED"}:
                if side == "buy" and (reserved_credits != amount or reserved_slh != ZERO):
                    errors.append("limit_buy_reservation_mismatch")
                if side == "sell" and (reserved_slh != amount or reserved_credits != ZERO):
                    errors.append("limit_sell_reservation_mismatch")
            elif reserved_credits != ZERO or reserved_slh != ZERO:
                errors.append("terminal_order_still_reserved")
        except (KeyError, InvalidOperation, TypeError, ValueError):
            errors.append("invalid_limit_order_numeric_field")
    if next_order_sequence and max_order_sequence >= next_order_sequence:
        errors.append("limit_order_sequence_ahead_of_counter")

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
