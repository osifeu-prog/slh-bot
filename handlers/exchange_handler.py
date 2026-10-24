from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
import json
import math
import time
import urllib.request
import state_manager
from core.exchange_gate import require_public_open  # compatibility/test seam; execution uses the fresh canonical check
from core.authority import is_owner
from core.slh_distribution import (
    is_frozen_account,
    reserve_in_db,
    release_reserve_in_db,
    settle_reserve_in_db,
)

ORDERS_KEY = "exchange_orders"
TRADES_KEY = "exchange_trades"
REQUESTS_KEY = "exchange_requests"
SEQ_KEY = "exchange_sequence"
SCALE = Decimal("0.00000001")
ZERO = Decimal("0")

EXCHANGE_PUBLIC_STATUS_URL = "https://slh-cloud-bot-production.up.railway.app/api/public/site-status"
EXCHANGE_PUBLIC_STATUS_TIMEOUT_SECONDS = 4
EXCHANGE_PUBLIC_STATUS_ATTEMPTS = 6
EXCHANGE_PUBLIC_STATUS_POLL_SECONDS = 2
EXCHANGE_PUBLIC_STATUS_MAX_AGE_SECONDS = 120


def _fetch_public_exchange_status():
    """Read the current public canonical beacon with cache bypass; never mutates state."""
    blocked = {
        "verified": False,
        "gate": "UNKNOWN",
        "readiness": False,
        "verdict": "UNKNOWN",
        "updated_at": None,
        "detail": "public runtime status unavailable",
    }
    request = urllib.request.Request(
        EXCHANGE_PUBLIC_STATUS_URL,
        headers={
            "Accept": "application/json",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(
            request, timeout=EXCHANGE_PUBLIC_STATUS_TIMEOUT_SECONDS
        ) as response:
            status = getattr(response, "status", None)
            if status is None:
                getcode = getattr(response, "getcode", None)
                status = getcode() if callable(getcode) else 200
            if status != 200:
                return {**blocked, "detail": f"public runtime status HTTP {status}"}
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        return {**blocked, "detail": f"public runtime probe failed: {type(exc).__name__}"}

    if not isinstance(payload, dict) or payload.get("ok") is not True:
        return {**blocked, "detail": "public runtime status returned no canonical proof"}

    system = payload.get("system")
    exchange = payload.get("exchange")
    if not isinstance(system, dict):
        system = {}
    if not isinstance(exchange, dict):
        exchange = {}

    gate = str(exchange.get("gate") or "UNKNOWN")
    verdict = str(exchange.get("verdict") or "UNKNOWN")
    readiness = exchange.get("readiness") is True
    updated_at = system.get("updated_at")
    timestamp_fresh = False
    try:
        timestamp = float(updated_at)
        age_seconds = time.time() - timestamp
        timestamp_fresh = (
            math.isfinite(timestamp)
            and -5 <= age_seconds <= EXCHANGE_PUBLIC_STATUS_MAX_AGE_SECONDS
        )
    except (TypeError, ValueError, OverflowError):
        timestamp_fresh = False

    verified = (
        str(system.get("status") or "").upper() == "ONLINE"
        and gate == "OPEN"
        and readiness
        and verdict == "OPEN"
        and timestamp_fresh
    )
    if verified:
        detail = "canonical public runtime proof passed"
    elif not timestamp_fresh:
        detail = "canonical public runtime timestamp is missing, stale, or from the future"
    else:
        detail = "canonical public runtime did not confirm ONLINE + OPEN + READY"
    return {
        "verified": verified,
        "gate": gate,
        "readiness": readiness,
        "verdict": verdict,
        "updated_at": updated_at,
        "detail": detail,
    }


def _wait_for_public_exchange_open(
    *, attempts=EXCHANGE_PUBLIC_STATUS_ATTEMPTS,
    delay_seconds=EXCHANGE_PUBLIC_STATUS_POLL_SECONDS,
):
    """Retry a read-only live proof briefly after deployment routing changes."""
    try:
        total_attempts = max(1, min(10, int(attempts)))
        delay = max(0.0, float(delay_seconds))
    except (TypeError, ValueError):
        total_attempts = EXCHANGE_PUBLIC_STATUS_ATTEMPTS
        delay = EXCHANGE_PUBLIC_STATUS_POLL_SECONDS

    result = {
        "verified": False,
        "gate": "UNKNOWN",
        "readiness": False,
        "verdict": "UNKNOWN",
        "updated_at": None,
        "detail": "public runtime verification was not attempted",
    }
    for index in range(total_attempts):
        result = _fetch_public_exchange_status()
        if result.get("verified") is True:
            return result
        if index + 1 < total_attempts and delay > 0:
            time.sleep(delay)
    return result


def _prepare_verified_exchange_broadcast_preview():
    """Prepare the fixed announcement only after a separate live OPEN proof; never sends."""
    from handlers.broadcast_handler import (
        EXCHANGE_BROADCAST_TEXT,
        EXCHANGE_BROADCAST_TTL_SECONDS,
        OWNER_TELEGRAM_ID,
        _exchange_broadcast_reply,
        prepare_exchange_broadcast,
    )

    draft = prepare_exchange_broadcast(str(OWNER_TELEGRAM_ID))
    if draft.get("status") != "PREPARED":
        return (
            "\n\n⚠️ Exchange אומת כפתוח, אך לא נוצרה טיוטת ברודקאסט.\n"
            + _exchange_broadcast_reply(draft)
            + "\nלא נשלחה הודעה לאף משתמש."
        )

    recipient_count = int(draft.get("target_count") or 0)
    if draft.get("audience_scope") == "failed_only":
        target_note = "✅ ניסיון חוזר ממוקד: רק נמענים שנכשלו בשידור הקודם."
        confirmation = "אשר ושלח ברודקאסט למסחר פנימי"
    elif draft.get("audience_scope") == "new_users_only":
        target_note = (
            "✅ קהל מצומצם בלבד: רק משתמשים עם חותמת יצירה מאומתת באזור זמן "
            "שנוצרו אחרי סיום השידור הקודם. משתמשים שלא ניתן לאמת — מוחרגים."
        )
        confirmation = "אשר ושלח ברודקאסט למסחר פנימי"
    elif draft.get("requires_duplicate_ack") is True:
        target_note = "⛔ טיוטה ישנה עם סיכון לכפילויות אינה ניתנת לאישור; נדרשת תצוגה חדשה."
        confirmation = "הכן תצוגה חדשה עם קהל בטוח"
    else:
        target_note = "קהל היעד הרגיל ננעל לתצוגה הזו."
        confirmation = "אשר ושלח ברודקאסט למסחר פנימי"

    return (
        "\n\n🧾 תצוגה מקדימה בלבד — לא נשלחה הודעה לאף משתמש.\n"
        f"👥 קהל היעד שננעל לתצוגה הזו: {recipient_count} משתמשים.\n"
        f"{target_note}\n"
        "אם רשימת הנמענים תשתנה לפני האישור, השליחה תיחסם ותידרש תצוגה חדשה.\n"
        f"טיוטה בתוקף ל־{EXCHANGE_BROADCAST_TTL_SECONDS // 60} דקות.\n\n"
        f"{EXCHANGE_BROADCAST_TEXT}\n\n"
        f"כדי לבצע שליחה אמיתית, אמור עכשיו במפורש: ״{confirmation}״.\n"
        "שלב האישור נשאר נפרד; רגע לפני השליחה יתבצעו שוב בדיקת Exchange קנונית ואימות קהל היעד."
    )


def _now():
    return datetime.now(timezone.utc).isoformat()


def _dec(value, name):
    try:
        x = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("INVALID_" + name.upper())
    if not x.is_finite() or x <= ZERO:
        raise ValueError("INVALID_" + name.upper())
    return x.quantize(SCALE)


def _s(x):
    return format(Decimal(x).quantize(SCALE), "f")


def _f(x):
    return float(Decimal(x).quantize(SCALE))


def _wallet(db, uid):
    user = db.get("users", {}).get(str(uid))
    if not user:
        raise ValueError("USER_NOT_FOUND")
    return user.setdefault("wallet", {})


def _get(w, field):
    return Decimal(str(w.get(field, 0) or 0))


def _set(w, field, value):
    x = Decimal(value).quantize(SCALE)
    if x < ZERO:
        raise ValueError("NEGATIVE_BALANCE")
    w[field] = _f(x)


def _ledger(db, uid, before, amount, reason, meta):
    amount = Decimal(amount).quantize(SCALE)
    after = before + amount
    db.setdefault("ledger", []).append({
        "time": _now(), "uid": str(uid),
        "before": _f(before), "amount": _f(amount), "after": _f(after),
        "reason": reason, "meta": meta,
    })


def _reserve(w, field):
    return _get(w, field)


def _set_reserve(w, field, value):
    _set(w, field, value)


def _next(db):
    db[SEQ_KEY] = int(db.get(SEQ_KEY, 0)) + 1
    return db[SEQ_KEY]


def _request_key(uid, message_id):
    return f"TG-EXCHANGE-{uid}-{message_id}"


def _new_order(db, uid, side, amount, price, request_id):
    seq = _next(db)
    oid = f"O{seq:010d}"
    order = {
        "id": oid, "uid": str(uid), "side": side,
        "original_amount": _s(amount), "remaining_amount": _s(amount),
        "limit_price": _s(price),
        "reserved_slh": _s(amount if side == "sell" else ZERO),
        "reserved_credits": _s(amount * price if side == "buy" else ZERO),
        "sequence": seq, "status": "open", "created_at": _now(),
        "client_request_id": request_id,
    }
    db.setdefault(ORDERS_KEY, {})[oid] = order
    return order


def _assert_invariants(db):
    users = db.get("users", {})
    orders = db.get(ORDERS_KEY, {})
    want_slh = {str(uid): ZERO for uid in users}
    want_cr = {str(uid): ZERO for uid in users}

    for o in orders.values():
        rem = Decimal(str(o.get("remaining_amount", "0")))
        if o.get("status") == "open":
            uid = str(o["uid"])
            if rem <= ZERO:
                raise ValueError("OPEN_ORDER_WITHOUT_REMAINING")
            if o["side"] == "sell":
                res = Decimal(str(o["reserved_slh"]))
                if res != rem:
                    raise ValueError("SELL_ORDER_RESERVE_MISMATCH")
                want_slh[uid] = want_slh.get(uid, ZERO) + res
            else:
                res = Decimal(str(o["reserved_credits"]))
                expected = rem * Decimal(str(o["limit_price"]))
                if res != expected:
                    raise ValueError("BUY_ORDER_RESERVE_MISMATCH")
                want_cr[uid] = want_cr.get(uid, ZERO) + res
        elif rem != ZERO:
            raise ValueError("CLOSED_ORDER_HAS_REMAINING")

    for uid, user in users.items():
        w = user.setdefault("wallet", {})
        rs = _reserve(w, "exchange_reserved_slh")
        rc = _reserve(w, "exchange_reserved_credits")
        total_slh = _get(w, "token_balance")
        live_slh = _get(w, "live_token_balance")
        if (
            rs < ZERO
            or rc < ZERO
            or total_slh < ZERO
            or live_slh < ZERO
            or _get(w, "credits") < ZERO
        ):
            raise ValueError("EXCHANGE_NEGATIVE_BALANCE")
        if live_slh > total_slh or rs > live_slh:
            raise ValueError("WALLET_LIVE_SLH_BACKING_BREACH")
        if rs != want_slh.get(str(uid), ZERO):
            raise ValueError("WALLET_SLH_RESERVE_MISMATCH")
        if rc != want_cr.get(str(uid), ZERO):
            raise ValueError("WALLET_CREDIT_RESERVE_MISMATCH")


def _match(db, incoming):
    orders = db.setdefault(ORDERS_KEY, {})
    trades = db.setdefault(TRADES_KEY, [])
    uid = str(incoming["uid"])
    remaining = Decimal(str(incoming["remaining_amount"]))
    limit = Decimal(str(incoming["limit_price"]))
    candidates = [
        o for o in orders.values()
        if o["id"] != incoming["id"]
        and o.get("status") == "open"
        and o.get("side") != incoming["side"]
        and str(o.get("uid")) != uid
        and not is_frozen_account(db, o.get("uid"))
    ]

    if incoming["side"] == "buy":
        candidates = [o for o in candidates if Decimal(str(o["limit_price"])) <= limit]
        candidates.sort(key=lambda o: (Decimal(str(o["limit_price"])), int(o["sequence"])))
    else:
        candidates = [o for o in candidates if Decimal(str(o["limit_price"])) >= limit]
        candidates.sort(key=lambda o: (-Decimal(str(o["limit_price"])), int(o["sequence"])))

    filled = ZERO
    for resting in candidates:
        if remaining <= ZERO:
            break

        rrem = Decimal(str(resting["remaining_amount"]))
        take = min(remaining, rrem)
        price = Decimal(str(resting["limit_price"]))
        buyer_uid = uid if incoming["side"] == "buy" else str(resting["uid"])
        seller_uid = str(resting["uid"]) if incoming["side"] == "buy" else uid
        buyer = _wallet(db, buyer_uid)
        seller = _wallet(db, seller_uid)
        cost = take * price
        buy = incoming if incoming["side"] == "buy" else resting
        sell = resting if incoming["side"] == "buy" else incoming
        buy_res = Decimal(str(buy["reserved_credits"]))
        sell_res = Decimal(str(sell["reserved_slh"]))
        bid = Decimal(str(buy["limit_price"]))
        if buy_res < take * bid or sell_res < take:
            raise ValueError("EXCHANGE_RESERVE_BREACH")

        tid = f"T{_next(db):010d}"
        _set_reserve(
            buyer, "exchange_reserved_credits",
            _reserve(buyer, "exchange_reserved_credits") - take * bid,
        )
        buy["reserved_credits"] = _s(buy_res - take * bid)
        buy["remaining_amount"] = _s(Decimal(str(buy["remaining_amount"])) - take)
        sell["reserved_slh"] = _s(sell_res - take)
        sell["remaining_amount"] = _s(Decimal(str(sell["remaining_amount"])) - take)

        settle_reserve_in_db(
            db,
            seller_uid=seller_uid,
            buyer_uid=buyer_uid,
            amount=take,
            event_id=f"exchange:settlement_slh:{tid}",
            order_id=sell["id"],
            trade_id=tid,
        )

        seller_before = _get(seller, "credits")
        _set(seller, "credits", seller_before + cost)
        _ledger(
            db, seller_uid, seller_before, cost, "exchange:settlement_credits",
            {"trade_id": tid, "order_id": sell["id"]},
        )

        improvement = take * (bid - price)
        if improvement > ZERO:
            before = _get(buyer, "credits")
            _set(buyer, "credits", before + improvement)
            _ledger(
                db, buyer_uid, before, improvement,
                "exchange:price_improvement_release",
                {"trade_id": tid, "order_id": buy["id"]},
            )

        trades.append({
            "id": tid, "buyer_uid": buyer_uid, "seller_uid": seller_uid,
            "slh_amount": _s(take), "price": _s(price), "credits_value": _s(cost),
            "timestamp": _now(), "buy_order_id": buy["id"], "sell_order_id": sell["id"],
        })
        filled += take
        remaining -= take
        if Decimal(str(resting["remaining_amount"])) == ZERO:
            resting["status"] = "filled"

    if remaining == ZERO:
        incoming["status"] = "filled"
    return filled, remaining


class ExchangeFreshCheckBlocked(ValueError):
    """Order entry was stopped by a fresh local or live canonical check."""

    def __init__(self, check, checked_at=None):
        self.check = {
            "status": "BLOCKED",
            "checked_at": str(checked_at or check.get("checked_at") or _now()),
            "verdict": str(check.get("verdict") or "BLOCKED"),
            "public_gate": str(check.get("public_gate") or "UNKNOWN"),
            "public_ready": check.get("public_ready"),
            "execution_ready": check.get("execution_ready") is True,
            "order_book_integrity": check.get("order_book_integrity"),
            "trade_integrity": check.get("trade_integrity"),
            "money_invariants": check.get("money_invariants"),
            "open_orders": int(check.get("open_orders") or 0),
            "detail": str(check.get("detail") or "fresh execution check blocked"),
        }
        for field in (
            "railway_configured",
            "live_runtime_check",
            "live_checked_at",
            "live_public_gate",
            "live_public_updated_at",
            "live_public_readiness",
            "live_public_verdict",
        ):
            if field in check:
                self.check[field] = check[field]
        super().__init__("EXCHANGE_FRESH_CHECK_BLOCKED")


def require_fresh_live_exchange_proof():
    """Require an uncached public runtime beacon and the Railway gate before a new order."""
    attempted_at = _now()
    try:
        from core.railway_control import control_plane_exchange_gate_status

        control_plane = control_plane_exchange_gate_status(timeout_seconds=4)
        configured = str(control_plane.get("configured") or "UNKNOWN")
    except Exception as exc:
        raise ExchangeFreshCheckBlocked(
            {
                "checked_at": attempted_at,
                "public_gate": "UNKNOWN",
                "verdict": "BLOCKED",
                "execution_ready": False,
                "detail": f"Railway gate proof unavailable: {type(exc).__name__}",
                "railway_configured": "UNKNOWN",
                "live_runtime_check": "BLOCKED",
                "live_checked_at": attempted_at,
            },
            checked_at=attempted_at,
        ) from None

    if configured != "1":
        gate = "CLOSED" if configured == "0" else "UNKNOWN"
        raise ExchangeFreshCheckBlocked(
            {
                "checked_at": attempted_at,
                "public_gate": gate,
                "verdict": "BLOCKED",
                "execution_ready": False,
                "detail": f"Railway Exchange gate is not configured OPEN (configured={configured})",
                "railway_configured": configured,
                "live_runtime_check": "BLOCKED",
                "live_checked_at": attempted_at,
                "live_public_gate": gate,
            },
            checked_at=attempted_at,
        )

    live = _fetch_public_exchange_status()
    if live.get("verified") is not True:
        gate = str(live.get("gate") or "UNKNOWN")
        if gate not in {"OPEN", "CLOSED"}:
            gate = "UNKNOWN"
        raise ExchangeFreshCheckBlocked(
            {
                "checked_at": attempted_at,
                "public_gate": gate,
                "verdict": "BLOCKED",
                "public_ready": live.get("readiness") is True,
                "execution_ready": False,
                "detail": str(live.get("detail") or "fresh public runtime proof did not pass"),
                "railway_configured": configured,
                "live_runtime_check": "BLOCKED",
                "live_checked_at": attempted_at,
                "live_public_gate": gate,
                "live_public_updated_at": live.get("updated_at"),
                "live_public_readiness": live.get("readiness") is True,
                "live_public_verdict": str(live.get("verdict") or "UNKNOWN"),
            },
            checked_at=attempted_at,
        )

    # Timestamp is captured after both independent checks complete.
    return {
        "status": "PASS",
        "checked_at": _now(),
        "railway_configured": configured,
        "public_gate": str(live.get("gate") or "OPEN"),
        "public_verdict": str(live.get("verdict") or "OPEN"),
        "public_readiness": live.get("readiness") is True,
        "public_updated_at": live.get("updated_at"),
        "public_detail": str(live.get("detail") or ""),
    }


def _place(db, uid, side, amount, price, request_id, live_proof=None):
    # Internal atomic order path. Public entry points must call
    # execute_exchange_order(), which verifies live state before opening this
    # transaction; this function still runs the local DB/environment check
    # against the exact snapshot that will be mutated.
    if is_frozen_account(db, uid):
        raise ValueError("ACCOUNT_FROZEN")

    # Final authorization check against the exact atomic DB snapshot.
    # This covers legacy callers that do not go through execute_exchange_order().
    from core.trader_certification import has_trader_certification
    if not has_trader_certification(uid, db):
        raise ValueError("TRADER_CERTIFICATION_REQUIRED")

    from core.system_checks import check_exchange_for_execution

    checked_at = _now()
    fresh_check = check_exchange_for_execution(db)
    if not fresh_check.get("execution_ready"):
        blocked_check = dict(fresh_check)
        if isinstance(live_proof, dict) and live_proof.get("status") == "PASS":
            blocked_check.update({
                "railway_configured": str(live_proof.get("railway_configured") or "UNKNOWN"),
                "live_runtime_check": "PASS",
                "live_checked_at": str(live_proof.get("checked_at") or ""),
                "live_public_gate": str(live_proof.get("public_gate") or "UNKNOWN"),
                "live_public_updated_at": live_proof.get("public_updated_at"),
                "live_public_readiness": live_proof.get("public_readiness") is True,
                "live_public_verdict": str(live_proof.get("public_verdict") or "UNKNOWN"),
            })
        raise ExchangeFreshCheckBlocked(blocked_check, checked_at=checked_at)
    trades_before = len(db.get(TRADES_KEY, []))
    w = _wallet(db, uid)
    order_id_preview = None

    if side == "sell":
        # The order ID is required for the canonical SLH reserve event, so
        # create the order before moving SLH into escrow.
        order = _new_order(db, uid, side, amount, price, request_id)
        order_id_preview = order["id"]
        reserve_in_db(
            db,
            uid=uid,
            amount=amount,
            event_id=f"exchange:reserve_slh:{order['id']}",
            order_id=order["id"],
        )
    else:
        reserve = amount * price
        available = _get(w, "credits")
        if available < reserve:
            raise ValueError("INSUFFICIENT_CREDITS")
        _set(w, "credits", available - reserve)
        _set_reserve(
            w, "exchange_reserved_credits",
            _reserve(w, "exchange_reserved_credits") + reserve,
        )
        order = _new_order(db, uid, side, amount, price, request_id)

        _ledger(
            db, uid, available, -reserve, "exchange:buy_reserve",
            {"order_id": order["id"], "request_id": request_id},
        )

    if side == "sell":
        # Preserve the general Credits ledger for buy-side accounting; SLH
        # accounting is canonicalized in slh_token_ledger only.
        pass

    filled, remaining = _match(db, order)
    trade_rows = db.get(TRADES_KEY, [])
    trade_ids = [
        str(trade.get("id"))
        for trade in trade_rows[trades_before:]
        if isinstance(trade, dict) and trade.get("id")
    ]
    execution_check = {
        "status": "PASS",
        "checked_at": checked_at,
        "public_gate": fresh_check.get("public_gate"),
        "verdict": fresh_check.get("verdict"),
        "execution_ready": bool(fresh_check.get("execution_ready")),
        "public_ready": bool(fresh_check.get("public_ready")),
        "order_book_integrity": bool(fresh_check.get("order_book_integrity")),
        "trade_integrity": bool(fresh_check.get("trade_integrity")),
        "money_invariants": bool(fresh_check.get("money_invariants")),
        "open_orders_before": int(fresh_check.get("open_orders") or 0),
    }
    if isinstance(live_proof, dict) and live_proof.get("status") == "PASS":
        execution_check.update({
            "live_runtime_check": "PASS",
            "live_checked_at": str(live_proof.get("checked_at") or ""),
            "live_railway_gate": str(live_proof.get("railway_configured") or "UNKNOWN"),
            "live_public_gate": str(live_proof.get("public_gate") or "UNKNOWN"),
            "live_public_verdict": str(live_proof.get("public_verdict") or "UNKNOWN"),
            "live_public_readiness": live_proof.get("public_readiness") is True,
            "live_public_updated_at": live_proof.get("public_updated_at"),
        })
    result = {
        "order_id": order["id"], "filled": _s(filled), "remaining": _s(remaining),
        "status": order["status"], "trade_ids": trade_ids,
        "execution_check": execution_check,
    }
    db.setdefault(REQUESTS_KEY, {})[request_id] = result
    _assert_invariants(db)
    return result


def _validate_existing_exchange_request_intent(
    db, existing, *, uid, side, amount, price, request_id
):
    """Validate REST idempotency keys against the originally stored order intent."""
    if not isinstance(existing, dict):
        raise ValueError("EXCHANGE_REQUEST_RECORD_INVALID")
    old_order_id = str(existing.get("order_id") or "")
    orders = db.get(ORDERS_KEY, {}) if isinstance(db, dict) else {}
    old_order = orders.get(old_order_id) if isinstance(orders, dict) else None
    if not isinstance(old_order, dict):
        raise ValueError("EXCHANGE_REQUEST_RECORD_INVALID")
    try:
        old_amount = _dec(old_order.get("original_amount"), "amount")
        old_price = _dec(old_order.get("limit_price"), "price")
    except ValueError as exc:
        raise ValueError("EXCHANGE_REQUEST_RECORD_INVALID") from exc

    same_intent = (
        str(old_order.get("uid")) == str(uid)
        and str(old_order.get("client_request_id") or "") == str(request_id)
        and str(old_order.get("side") or "").strip().lower() == str(side).lower()
        and old_amount == amount
        and old_price == price
    )
    if not same_intent:
        raise ValueError("EXCHANGE_IDEMPOTENCY_KEY_REUSED")
    return existing


def _existing_exchange_request(
    request_id, *, uid=None, side=None, amount=None, price=None,
    strict_replay=False, db=None
):
    """Read an idempotent receipt and optionally validate the original intent."""
    db = state_manager.load_db() if db is None else db
    requests = db.get(REQUESTS_KEY, {}) if isinstance(db, dict) else {}
    existing = requests.get(str(request_id)) if isinstance(requests, dict) else None
    if existing is not None and strict_replay:
        return _validate_existing_exchange_request_intent(
            db, existing, uid=uid, side=side, amount=amount, price=price,
            request_id=request_id,
        )
    return existing


def execute_exchange_order(
    *, uid, side, amount, price, request_id,
    strict_replay=False, include_replay_marker=False,
):
    """Execute one Buy/Sell only after live gate proof, preserving replay receipts.

    Network calls happen before the atomic DB mutation. The final local invariant
    check remains inside _place() against the exact snapshot being changed.
    Strict REST replays also retain the original request-intent binding.
    """
    request_id = str(request_id or "").strip()
    if not request_id:
        raise ValueError("EXCHANGE_REQUEST_ID_REQUIRED")
    uid = str(uid)
    side = str(side or "").strip().lower()
    if side not in {"buy", "sell"}:
        raise ValueError("INVALID_EXCHANGE_SIDE")

    def response(result, replayed):
        if include_replay_marker and isinstance(result, dict):
            return {**result, "idempotent_replay": bool(replayed)}
        return result

    existing = _existing_exchange_request(
        request_id, uid=uid, side=side, amount=amount, price=price,
        strict_replay=strict_replay,
    )
    if existing is not None:
        return response(existing, True)

    # Check the canonical global gate before per-user authorization. When the
    # market is closed for everyone, report that global state first instead of
    # misleading an uncertified user with an account-specific permission error.
    try:
        live_proof = require_fresh_live_exchange_proof()
    except ExchangeFreshCheckBlocked:
        # A concurrent replay may have committed while the live proof was read.
        # Return its saved receipt rather than misreporting a prior order as new
        # or encouraging the client to submit a duplicate.
        existing = _existing_exchange_request(
            request_id, uid=uid, side=side, amount=amount, price=price,
            strict_replay=strict_replay,
        )
        if existing is not None:
            return response(existing, True)
        raise

    # The central execution service is shared by Telegram and authenticated Mini App/API.
    # Trader certification is still mandatory once the canonical global gate is open.
    from core.trader_certification import has_trader_certification
    if not has_trader_certification(uid):
        raise ValueError("TRADER_CERTIFICATION_REQUIRED")

    replayed = {"value": False}

    def mutate(db):
        requests = db.setdefault(REQUESTS_KEY, {})
        if not isinstance(requests, dict):
            raise ValueError("EXCHANGE_REQUEST_STORE_INVALID")
        existing_result = requests.get(request_id)
        if existing_result is not None:
            if strict_replay:
                existing_result = _validate_existing_exchange_request_intent(
                    db, existing_result, uid=uid, side=side, amount=amount,
                    price=price, request_id=request_id,
                )
            replayed["value"] = True
            return existing_result
        replayed["value"] = False
        return _place(
            db, uid, side, amount, price, request_id, live_proof=live_proof
        )

    result = state_manager.atomic_update(mutate)
    return response(result, replayed["value"])


def format_execution_receipt(side, result):
    """Render an order result alongside its fresh canonical send-time check.

    Missing or partial check data must never be described as a passing receipt.
    """
    result = result if isinstance(result, dict) else {}
    check = result.get("execution_check")
    check = check if isinstance(check, dict) else {}
    side_label = str(side or "order").strip().upper()
    order_id = str(result.get("order_id") or "UNKNOWN")
    filled = str(result.get("filled") or "0")
    remaining = str(result.get("remaining") or "0")
    checked_at = str(check.get("checked_at") or "unavailable")
    gate = str(check.get("public_gate") or "UNKNOWN")
    verdict = str(check.get("verdict") or "UNKNOWN")

    required_flags = (
        "execution_ready",
        "public_ready",
        "order_book_integrity",
        "trade_integrity",
        "money_invariants",
    )
    check_present = bool(check) and checked_at != "unavailable"
    all_checks_pass = (
        check.get("status") == "PASS"
        and gate == "OPEN"
        and verdict == "OPEN"
        and all(check.get(flag) is True for flag in required_flags)
    )
    live_check_pass = (
        check.get("live_runtime_check") == "PASS"
        and check.get("live_railway_gate") == "1"
        and check.get("live_public_gate") == "OPEN"
        and check.get("live_public_verdict") == "OPEN"
        and check.get("live_public_readiness") is True
        and bool(check.get("live_checked_at"))
    )
    receipt_icon = "✅" if all_checks_pass and live_check_pass else "⚠️"
    if not check_present:
        check_status = "NOT VERIFIED"
    elif all_checks_pass:
        check_status = "PASS"
    else:
        check_status = "BLOCKED"

    def _flag(name):
        if name not in check:
            return "UNKNOWN"
        return "PASS" if check.get(name) is True else "FAIL"

    trade_ids = result.get("trade_ids")
    trade_ids = [str(t) for t in trade_ids if t] if isinstance(trade_ids, list) else []
    trade_text = ", ".join(trade_ids) if trade_ids else "none (order may remain open)"

    lines = [
        f"{receipt_icon} {side_label} #{order_id} | filled {filled} | open {remaining} SLH",
        f"🔐 Fresh canonical Exchange check: {check_status}",
        f"🕒 checked_at (UTC): {checked_at}",
        f"Gate: {gate} | verdict: {verdict}",
        f"execution_ready: {_flag('execution_ready')}",
        f"public_ready: {_flag('public_ready')}",
        f"order_book_integrity: {_flag('order_book_integrity')}",
        f"trade_integrity: {_flag('trade_integrity')}",
        f"money_invariants: {_flag('money_invariants')}",
        f"🌐 Fresh live runtime confirmation: {'PASS' if live_check_pass else 'NOT VERIFIED'}",
        f"Railway configured gate: {str(check.get('live_railway_gate') or 'UNKNOWN')}",
        f"Live public gate/verdict: {str(check.get('live_public_gate') or 'UNKNOWN')} / {str(check.get('live_public_verdict') or 'UNKNOWN')}",
        f"Live public beacon updated_at: {str(check.get('live_public_updated_at') or 'unavailable')}",
        f"Trade IDs: {trade_text}",
    ]
    if check_status != "PASS":
        lines.append("⚠️ Receipt does not prove a passing fresh execution check.")
    elif not live_check_pass:
        lines.append("⚠️ Fresh live runtime gate proof is missing; do not use this as a verified new-order receipt.")
    return "\n".join(lines)


def format_blocked_execution_receipt(side, check):
    """Render a fail-closed order-entry receipt for Telegram."""
    check = check if isinstance(check, dict) else {}
    side_label = str(side or "order").strip().upper()
    checked_at = str(check.get("checked_at") or "unavailable")
    gate = str(check.get("public_gate") or "UNKNOWN")
    verdict = str(check.get("verdict") or "UNKNOWN")
    detail = str(check.get("detail") or "fresh canonical check did not pass")
    check_status = (
        "BLOCKED"
        if check.get("status") == "BLOCKED" and checked_at != "unavailable"
        else "NOT VERIFIED"
    )

    def _flag(name):
        if name not in check or check.get(name) is None:
            return "UNKNOWN"
        return "PASS" if check.get(name) is True else "FAIL"

    lines = [
        f"⛔ {side_label} not executed",
        f"🔐 Fresh canonical Exchange check: {check_status}",
        f"🕒 checked_at (UTC): {checked_at}",
        f"Gate: {gate} | verdict: {verdict}",
        f"execution_ready: {_flag('execution_ready')}",
        f"public_ready: {_flag('public_ready')}",
        f"order_book_integrity: {_flag('order_book_integrity')}",
        f"trade_integrity: {_flag('trade_integrity')}",
        f"money_invariants: {_flag('money_invariants')}",
        f"🌐 Fresh live runtime confirmation: {str(check.get('live_runtime_check') or 'NOT VERIFIED')}",
        f"Railway configured gate: {str(check.get('railway_configured') or 'UNKNOWN')}",
        f"Live public gate/verdict: {str(check.get('live_public_gate') or check.get('public_gate') or 'UNKNOWN')} / {str(check.get('live_public_verdict') or 'UNKNOWN')}",
        f"Reason: {detail}",
    ]
    if check_status == "BLOCKED":
        lines.append(
            "No order was placed or balances changed. Refresh Exchange state before trying again."
        )
    else:
        lines.append(
            "The server did not provide a complete fresh-check receipt; do not retry until the order/history is checked."
        )
    return "\n".join(lines)


def _request_guarded_exchange_gate_open():
    """Open only with fresh launch proof, then verify the new live runtime before previewing."""
    try:
        db = state_manager.load_db()
        from core.system_checks import check_exchange

        check = check_exchange(db, for_execution=False)
    except Exception as exc:
        return f"⛔ Exchange נשאר סגור. בדיקת המוכנות נכשלה: {type(exc).__name__}."

    runtime_open = check.get("public_gate") == "OPEN"
    runtime_clean = (
        check.get("verdict") == "OPEN"
        and check.get("public_ready") is True
        and check.get("order_book_integrity") is True
        and check.get("trade_integrity") is True
        and check.get("money_invariants") is True
    )

    if runtime_open:
        if not runtime_clean:
            return (
                "🔴 EXCHANGE OPEN — RUNTIME NOT READY / DO NOT TRADE OR ANNOUNCE.\n"
                f"verdict={check.get('verdict', 'UNKNOWN')} · "
                f"public_ready={check.get('public_ready', 'UNKNOWN')} · "
                f"orders={check.get('open_orders', 'UNKNOWN')}\n"
                f"פרטים: {str(check.get('detail') or 'הבדיקה הקנונית לא עברה')[:240]}\n"
                "לא נוצרה טיוטת ברודקאסט ולא נשלחה הודעה."
            )

        try:
            from core.railway_control import (
                control_plane_exchange_gate_status,
                safe_railway_error_code,
            )
            configured = control_plane_exchange_gate_status().get("configured")
        except Exception as exc:
            from core.railway_control import safe_railway_error_code
            code = safe_railway_error_code(exc)
            return (
                f"🟡 EXCHANGE OPEN — NOT VERIFIED ACROSS CONTROL PLANE ({code}).\n"
                "לא נוצרה טיוטת ברודקאסט ולא נשלחה הודעה."
            )

        if configured != "1":
            return (
                f"🟡 EXCHANGE OPEN — NOT VERIFIED: Control Plane configured={configured}.\n"
                "אין להכריז על פתיחת המסחר. לא נוצרה טיוטת ברודקאסט ולא נשלחה הודעה."
            )

        live = _wait_for_public_exchange_open()
        if live.get("verified") is not True:
            return (
                "🟡 EXCHANGE OPEN — RUNTIME NOT VERIFIED / DO NOT ANNOUNCE.\n"
                f"בדיקת runtime קנונית: gate={live.get('gate', 'UNKNOWN')} · "
                f"readiness={live.get('readiness', False)} · "
                f"verdict={live.get('verdict', 'UNKNOWN')}.\n"
                f"פרטים: {live.get('detail', 'No live proof')}\n"
                "לא נוצרה טיוטת ברודקאסט ולא נשלחה הודעה. בדוק /exchange_gate status."
            )

        return (
            "✅ EXCHANGE OPEN VERIFIED — EXECUTION CHECKS PASS\n"
            "ה־runtime החי אומת מול מקור האמת הקנוני. לא בוצע שינוי בשער.\n"
            + _prepare_verified_exchange_broadcast_preview()
        )

    clean = (
        check.get("ok") is True
        and check.get("public_gate") == "CLOSED"
        and check.get("verdict") == "READY_TO_OPEN"
        and check.get("public_ready") is True
        and check.get("order_book_integrity") is True
        and check.get("trade_integrity") is True
        and check.get("money_invariants") is True
        and check.get("account_ledger_status") == "PASS"
        and check.get("account_ledger_integrity") is True
        and check.get("open_orders") == 0
        and check.get("test_seed_open") == 0
        and check.get("test_seed_trades") == 0
    )
    if not clean:
        return (
            "⛔ Exchange gate נשאר CLOSED — לא בוצע שינוי.\n"
            f"Fresh canonical check: gate={check.get('public_gate', 'UNKNOWN')} · "
            f"verdict={check.get('verdict', 'UNKNOWN')} · "
            f"public_ready={check.get('public_ready', 'UNKNOWN')}\n"
            f"Orders={check.get('open_orders', 'UNKNOWN')} · "
            f"test/seed orders={check.get('test_seed_open', 'UNKNOWN')} · "
            f"test/seed trades={check.get('test_seed_trades', 'UNKNOWN')}\n"
            f"פרטים: {str(check.get('detail') or 'הבדיקה לא עמדה בכל התנאים')[:240]}"
        )

    proof = {
        "status": "PASS",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "public_gate": "CLOSED",
        "verdict": "READY_TO_OPEN",
        "public_ready": True,
        "order_book_integrity": True,
        "trade_integrity": True,
        "money_invariants": True,
        # Forward the result of the canonical owner-ledger audit; never synthesize PASS.
        "account_ledger_status": check.get("account_ledger_status"),
        "account_ledger_integrity": check.get("account_ledger_integrity"),
        "open_orders": 0,
        "test_seed_open": 0,
        "test_seed_trades": 0,
    }
    try:
        from core.railway_control import request_exchange_gate_open, safe_railway_error_code

        result = request_exchange_gate_open(proof)
    except Exception as exc:
        from core.railway_control import safe_railway_error_code

        code = safe_railway_error_code(exc)
        return (
            f"⛔ בקשת פתיחה לא אושרה: {code}. Exchange נשאר CLOSED או לא אומת; "
            "לא נשלח ברודקאסט."
        )

    live = _wait_for_public_exchange_open()
    if live.get("verified") is not True:
        return (
            "🟡 EXCHANGE DEPLOYMENT SUCCESS — RUNTIME NOT VERIFIED.\n"
            "Railway דיווח על פריסה שהסתיימה ב־SUCCESS, אך מקור האמת החי עדיין לא אישר "
            "ONLINE + OPEN + READY.\n"
            f"פרטים: {live.get('detail', 'No live proof')} · "
            f"gate={live.get('gate', 'UNKNOWN')} · readiness={live.get('readiness', False)} · "
            f"verdict={live.get('verdict', 'UNKNOWN')}.\n"
            "לא נוצרה טיוטת ברודקאסט ולא נשלחה הודעה. אין להכריז שהמסחר פתוח; "
            "בדוק /exchange_gate status. BNB ו־TON לא שונו."
        )

    return (
        "✅ EXCHANGE OPEN VERIFIED — EXECUTION CHECKS PASS\n"
        "בדיקת המוכנות לפני הפתיחה עברה, הפריסה הסתיימה ב־SUCCESS, וה־runtime החדש "
        "אישר ONLINE + OPEN + READY ממקור האמת הקנוני.\n"
        f"Commit: {result['commit'][:12]}\n"
        f"Deployment ID: {result['deployment_id']}\n"
        + _prepare_verified_exchange_broadcast_preview()
    )

def _matches_exchange_gate_open_phrase(text):
    """Exact phrase allowlist shared by owner voice and typed-text controls."""
    from handlers.broadcast_handler import _normalize_voice_phrase

    phrase = _normalize_voice_phrase(str(text or ""))
    allowed = {
        _normalize_voice_phrase("פתח מסחר פנימי אם בדיקת המוכנות הקנונית עוברת"),
        _normalize_voice_phrase("פתח את המסחר הפנימי אם בדיקת המוכנות הקנונית עוברת"),
        _normalize_voice_phrase("פתח מסחר פנימי רק אם בדיקת המוכנות הקנונית עוברת"),
        _normalize_voice_phrase("פתח את המסחר הפנימי רק אם בדיקת המוכנות הקנונית עוברת"),
        _normalize_voice_phrase("פתח מסחר פנימי אם בדיקת מוכנות קנונית עוברת"),
    }
    return phrase in allowed


def _is_exchange_gate_text_message(message):
    """Pure filter: do not perform an operation while Telegram evaluates handlers."""
    return _matches_exchange_gate_open_phrase(getattr(message, "text", ""))


def route_exchange_gate_text(bot, message, text):
    """Route one exact typed owner request to the same guarded open path as voice."""
    if not _matches_exchange_gate_open_phrase(text):
        return None

    uid = getattr(getattr(message, "from_user", None), "id", None)
    if not is_owner(uid):
        return "⛔ רק OWNER יכול לבקש פתיחת Exchange."
    if str(getattr(getattr(message, "chat", None), "type", "")).lower() != "private":
        return "⛔ פתיחת Exchange זמינה רק בשיחה הפרטית עם הבוט."
    return _request_guarded_exchange_gate_open()


def route_exchange_gate_voice(bot, message, transcript):
    """Handle only an exact owner/private voice request for guarded Exchange opening."""
    if not _matches_exchange_gate_open_phrase(transcript):
        return None

    uid = getattr(getattr(message, "from_user", None), "id", None)
    if not is_owner(uid):
        return "⛔ רק OWNER יכול לבקש פתיחת Exchange."
    if str(getattr(getattr(message, "chat", None), "type", "")).lower() != "private":
        return "⛔ פתיחת Exchange בקול זמינה רק בשיחה הפרטית עם הבוט."
    return _request_guarded_exchange_gate_open()


def build_exchange_chart_url(base_url=None):
    """Build a validated HTTPS Mini App deep link for the internal Exchange screen."""
    import os
    from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

    configured = base_url if base_url is not None else os.getenv("SLH_MINI_APP_URL", "")
    base = str(configured or "").strip()
    if not base:
        base = "https://slh-cloud-bot-production.up.railway.app/mini-app-v4"

    parsed = urlsplit(base)
    if parsed.scheme.lower() != "https" or not parsed.netloc:
        parsed = urlsplit("https://slh-cloud-bot-production.up.railway.app/mini-app-v4")

    path = parsed.path or "/mini-app-v4"
    query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key not in {"screen", "chart"}
    ]
    query.extend((("screen", "exchange"), ("chart", "1")))
    return urlunsplit((parsed.scheme, parsed.netloc, path, urlencode(query), ""))


def register(bot):
    @bot.message_handler(commands=["chart"])
    def exchange_chart_cmd(msg):
        chat_type = str(getattr(getattr(msg, "chat", None), "type", "")).lower()
        if chat_type != "private":
            bot.reply_to(msg, "פתח את /chart בשיחה הפרטית עם הבוט כדי לפתוח את Mini App.")
            return
        try:
            from telebot import types

            url = build_exchange_chart_url()
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton(
                    "📈 פתח את בורסת SLH",
                    web_app=types.WebAppInfo(url=url),
                )
            )
            bot.reply_to(
                msg,
                "📈 SLH Exchange — גרף מחיר\n\n"
                "פתיחת מסך הבורסה ישירות בתוך Telegram. "
                "הנרות מבוססים על עסקאות פנימיות שהושלמו בלבד; "
                "כאשר יש מעט עסקאות, ההיסטוריה תהיה דלילה. "
                "זה אינו מחיר DEX או הצהרה על נזילות חיצונית.",
                reply_markup=markup,
            )
        except Exception:
            bot.reply_to(
                msg,
                "❌ לא הצלחתי לפתוח את קישור הבורסה. פתח את /miniapp ונווט אל 🪙 בורסה.",
            )

    @bot.message_handler(func=_is_exchange_gate_text_message, content_types=["text"])
    def exchange_gate_text_cmd(msg):
        answer = route_exchange_gate_text(bot, msg, getattr(msg, "text", "") or "")
        if answer is not None:
            bot.reply_to(msg, answer, parse_mode=None)

    @bot.message_handler(commands=["exchange_gate"])
    def exchange_gate_cmd(msg):
        if not is_owner(msg.from_user.id):
            bot.reply_to(msg, "⛔ OWNER only")
            return
        if str(getattr(getattr(msg, "chat", None), "type", "")).lower() != "private":
            bot.reply_to(msg, "⛔ פקודת Exchange gate זמינה רק בפרטי.")
            return

        parts = (msg.text or "").split()
        action = parts[1].lower() if len(parts) > 1 else "status"
        if len(parts) > 2 or action not in {"status", "open", "close"}:
            bot.reply_to(msg, "שימוש: /exchange_gate status  או  /exchange_gate open  או  /exchange_gate close")
            return

        if action == "open":
            bot.reply_to(msg, _request_guarded_exchange_gate_open())
            return

        if action == "status":
            import os
            from core.exchange_gate import public_open
            from core.railway_control import (
                control_plane_exchange_gate_status,
                safe_railway_error_code,
            )
            from core.system_checks import check_exchange_for_execution

            runtime_env = (os.getenv("SLH_EXCHANGE_PUBLIC_OPEN", "0") or "0").strip()
            try:
                check = check_exchange_for_execution(state_manager.load_db())
            except Exception:
                check = {
                    "public_gate": "UNKNOWN",
                    "execution_ready": None,
                    "open_orders": "UNKNOWN",
                }
            try:
                railway = control_plane_exchange_gate_status()
                configured = railway.get("configured", "UNKNOWN")
                railway_problem = None
            except Exception as exc:
                configured = "UNKNOWN"
                railway_problem = safe_railway_error_code(exc)

            runtime_open = public_open()
            verified_closed = (
                configured == "0"
                and runtime_env == "0"
                and runtime_open is False
                and check.get("public_gate") == "CLOSED"
                and check.get("execution_ready") is False
            )
            verified_open = (
                configured == "1"
                and runtime_env == "1"
                and runtime_open is True
                and check.get("public_gate") == "OPEN"
                and check.get("verdict") == "OPEN"
                and check.get("execution_ready") is True
                and check.get("public_ready") is True
                and check.get("order_book_integrity") is True
                and check.get("trade_integrity") is True
                and check.get("money_invariants") is True
            )
            if verified_closed:
                state = "✅ CLOSED VERIFIED"
            elif verified_open:
                state = "✅ OPEN VERIFIED — EXECUTION CHECKS PASS"
            elif runtime_open is True or runtime_env == "1":
                state = "🔴 OPEN — RUNTIME NOT READY / DO NOT TRADE"
            elif configured == "1":
                state = "🟡 OPEN CONFIGURED — RUNTIME NOT VERIFIED; DO NOT ANNOUNCE"
            else:
                state = "🟡 NOT VERIFIED — KEEP CLOSED"

            lines = [
                "🛡️ SLH EXCHANGE GATE — OWNER / READ ONLY",
                f"Railway Production variable: {configured}",
                f"Runtime env: {runtime_env if runtime_env in {'0', '1'} else 'INVALID'}",
                f"Effective gate: {check.get('public_gate', 'UNKNOWN')}",
                f"execution_ready: {check.get('execution_ready', 'UNKNOWN')}",
                f"Open orders: {check.get('open_orders', 'UNKNOWN')}",
                f"Status: {state}",
            ]
            if railway_problem:
                lines.append(f"Railway API diagnostic: {railway_problem}")
                if railway_problem == "RAILWAY_CONTROL_TOKEN_MISSING":
                    lines.append("The Control Plane service is missing its Railway API credential. Configure it only in the authorized Control Plane service; never add it to the bot or paste it into Telegram.")
                elif railway_problem == "RAILWAY_ACCESS_DENIED":
                    lines.append("The configured Railway token lacks access to this project/service. Use a token with access to slh-cloud-bot Production.")
                elif railway_problem == "CONTROL_PLANE_BRIDGE_AUTH_FAILED":
                    lines.append("The authenticated Control Plane bridge rejected the request. Keep Exchange closed and verify the shared bridge configuration.")
                elif railway_problem == "CONTROL_PLANE_BRIDGE_UNAVAILABLE":
                    lines.append("The Control Plane bridge is unavailable. Keep Exchange closed; do not infer the Railway value.")
            lines += [
                "",
                "Closing blocks new Buy/Sell orders; it does not cancel existing open orders or reverse prior trades.",
            ]
            bot.reply_to(msg, "\n".join(lines))
            return

        try:
            from core.railway_control import request_exchange_gate_close, safe_railway_error_code
            result = request_exchange_gate_close()
            bot.reply_to(
                msg,
                "🛡️ EXCHANGE CLOSE REQUEST ACCEPTED\n"
                "Railway Production variable verified: SLH_EXCHANGE_PUBLIC_OPEN=0\n"
                "Deployment triggered for slh-cloud-bot.\n"
                f"Commit: {result['commit'][:12]}\n"
                f"Deployment ID: {result['deployment_id']}\n\n"
                "The close is NOT marked complete until /exchange_gate status reports CLOSED VERIFIED after the service restarts. Do not announce or use Exchange before that verification."
            )
        except Exception as exc:
            from core.railway_control import safe_railway_error_code
            code = safe_railway_error_code(exc)
            hint = ""
            if code == "RAILWAY_CONTROL_TOKEN_MISSING":
                hint = " The Control Plane service needs its Railway API credential; configure it only there, never in the bot or in Telegram."
            elif code == "RAILWAY_ACCESS_DENIED":
                hint = " The configured Railway token lacks access to slh-cloud-bot Production."
            elif code == "CONTROL_PLANE_BRIDGE_AUTH_FAILED":
                hint = " The authenticated Control Plane bridge rejected the request; verify the shared bridge configuration."
            elif code == "CONTROL_PLANE_BRIDGE_UNAVAILABLE":
                hint = " The Control Plane bridge is unavailable; no close is verified."
            bot.reply_to(
                msg,
                f"⛔ Exchange close not verified: {code}.{hint} "
                "Run /exchange_gate status after credential setup; do not assume the live gate is closed."
            )

    @bot.message_handler(commands=["exchange_clean", "exchange_cleanup"])
    def exchange_clean_cmd(msg):
        if not is_owner(msg.from_user.id):
            bot.reply_to(msg, "⛔ OWNER only")
            return
        try:
            parts = (msg.text or "").split()
            from core.exchange_housekeeping import archive_test_state, preview
            if len(parts) == 1:
                result = preview()
                text = (
                    "🧹 SLH EXCHANGE CLEANUP — OWNER ONLY\n\n"
                    f"Test/seed trades: {result['test_seed_trades']}\n"
                    f"Linked test/seed orders: {result['test_seed_orders']}\n"
                )
                if result["test_seed_trades"] or result["test_seed_orders"]:
                    text += "\nNothing changed.\nTo archive only classified test/seed state: /exchange_clean CONFIRM"
                else:
                    text += "\n✅ No classified test/seed exchange state remains."
                bot.reply_to(msg, text)
                return

            if len(parts) != 2 or parts[1] != "CONFIRM":
                bot.reply_to(
                    msg,
                    "שימוש: /exchange_clean — preview בלבד\n"
                    "או: /exchange_clean CONFIRM — archive קנוני של test/seed בלבד"
                )
                return

            result = archive_test_state(str(msg.from_user.id))
            from core.system_checks import check_exchange
            after = check_exchange()
            bot.reply_to(
                msg,
                "✅ Exchange test/seed state archived safely.\n"
                f"Archived trades: {result['archived_trades']}\n"
                f"Archived orders: {result['archived_orders']}\n"
                f"Post-check verdict: {after['verdict']}\n"
                f"Post-check readiness: {'PASS' if after['public_ready'] else 'FAIL'}\n"
                "🔒 Live customer orders/trades are never selected by this command."
            )
        except ValueError as exc:
            bot.reply_to(msg, "⛔ " + str(exc))
        except Exception as exc:
            bot.reply_to(msg, f"❌ Exchange cleanup failed safely: {type(exc).__name__}")

    @bot.message_handler(commands=["sell_slh"])
    def sell_slh(msg):
        parts = msg.text.split()
        if len(parts) != 3:
            bot.reply_to(msg, "שימוש: /sell_slh <amount_slh> <price_in_credits>")
            return
        try:
            amount, price = _dec(parts[1], "amount"), _dec(parts[2], "price")
            uid, key = str(msg.from_user.id), _request_key(msg.from_user.id, msg.message_id)

            r = execute_exchange_order(
                uid=uid, side="sell", amount=amount, price=price, request_id=key
            )
            bot.reply_to(msg, format_execution_receipt("sell", r))
        except ExchangeFreshCheckBlocked as e:
            bot.reply_to(msg, format_blocked_execution_receipt("SELL", e.check))
        except ValueError as e:
            if str(e) == "TRADER_CERTIFICATION_REQUIRED":
                bot.reply_to(msg, "🔒 כדי לסחור ב-SLH Exchange יש להשלים את הקורס ולעבור את המבחן: /courses ואז /trader_test")
            else:
                bot.reply_to(msg, "❌ " + str(e))
        except Exception as e:
            bot.reply_to(msg, "❌ שגיאה: " + str(e))

    @bot.message_handler(commands=["buy_slh"])
    def buy_slh(msg):
        parts = msg.text.split()
        if len(parts) != 3:
            bot.reply_to(msg, "שימוש: /buy_slh <amount_slh> <max_price_in_credits>")
            return
        try:
            amount, price = _dec(parts[1], "amount"), _dec(parts[2], "price")
            uid, key = str(msg.from_user.id), _request_key(msg.from_user.id, msg.message_id)

            r = execute_exchange_order(
                uid=uid, side="buy", amount=amount, price=price, request_id=key
            )
            bot.reply_to(msg, format_execution_receipt("buy", r))
        except ExchangeFreshCheckBlocked as e:
            bot.reply_to(msg, format_blocked_execution_receipt("BUY", e.check))
        except ValueError as e:
            if str(e) == "TRADER_CERTIFICATION_REQUIRED":
                bot.reply_to(msg, "🔒 כדי לסחור ב-SLH Exchange יש להשלים את הקורס ולעבור את המבחן: /courses ואז /trader_test")
            else:
                bot.reply_to(msg, "❌ " + str(e))
        except Exception as e:
            bot.reply_to(msg, "❌ שגיאה: " + str(e))

    @bot.message_handler(commands=["orders"])
    def orders_cmd(msg):
        db = state_manager.load_db()
        rows = [o for o in db.get(ORDERS_KEY, {}).values() if o.get("status") == "open"]
        rows.sort(key=lambda o: int(o["sequence"]))
        if not rows:
            bot.reply_to(msg, "אין הוראות פתוחות")
            return
        bot.reply_to(msg, "📖 הוראות פתוחות:\n" + "\n".join(
            f"#{o['id']} {o['side']} {o['remaining_amount']} SLH @ {o['limit_price']} C"
            for o in rows[:30]
        ))

    @bot.message_handler(commands=["trades"])
    def trades_cmd(msg):
        db = state_manager.load_db()
        rows = db.get(TRADES_KEY, [])[-10:]
        if not rows:
            bot.reply_to(msg, "אין עסקאות עדיין")
            return
        bot.reply_to(msg, "📊 עסקאות אחרונות:\n" + "\n".join(
            f"{t['id']} | {t['slh_amount']} SLH @ {t['price']} C" for t in rows
        ))

    @bot.message_handler(commands=["cancel"])
    def cancel_cmd(msg):
        parts = msg.text.split()
        if len(parts) != 2:
            bot.reply_to(msg, "שימוש: /cancel <order_id>")
            return
        oid, uid = parts[1], str(msg.from_user.id)

        def mutate(db):
            o = db.setdefault(ORDERS_KEY, {}).get(oid)
            if not o or str(o.get("uid")) != uid or o.get("status") != "open":
                raise ValueError("ORDER_NOT_FOUND_OR_NOT_YOURS")
            w = _wallet(db, uid)
            rem = Decimal(str(o["remaining_amount"]))
            if o["side"] == "sell":
                res = Decimal(str(o["reserved_slh"]))
                if res != rem:
                    raise ValueError("ORDER_RESERVE_MISMATCH")
                release_reserve_in_db(
                    db,
                    uid=uid,
                    amount=res,
                    event_id=f"exchange:release_slh:{oid}",
                    order_id=oid,
                )
                o["reserved_slh"] = _s(ZERO)
            else:
                res = Decimal(str(o["reserved_credits"]))
                expected = rem * Decimal(str(o["limit_price"]))
                if res != expected:
                    raise ValueError("ORDER_RESERVE_MISMATCH")
                _set_reserve(
                    w, "exchange_reserved_credits",
                    _reserve(w, "exchange_reserved_credits") - res,
                )
                before = _get(w, "credits")
                _set(w, "credits", before + res)
                _ledger(
                    db, uid, before, res, "exchange:cancel_release_credits",
                    {"order_id": oid},
                )
                o["reserved_credits"] = _s(ZERO)
            o["remaining_amount"] = _s(ZERO)
            o["status"] = "cancelled"
            _assert_invariants(db)
            return True

        try:
            state_manager.atomic_update(mutate)
            bot.reply_to(msg, f"✅ הוראה #{oid} בוטלה")
        except ValueError as e:
            bot.reply_to(msg, "❌ " + str(e))
        except Exception as e:
            bot.reply_to(msg, "❌ שגיאה: " + str(e))
