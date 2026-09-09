from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
import state_manager

ORDERS_KEY = "exchange_orders"
TRADES_KEY = "exchange_trades"
REQUESTS_KEY = "exchange_requests"
SEQ_KEY = "exchange_sequence"
SCALE = Decimal("0.00000001")
ZERO = Decimal("0")


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
        if rs < ZERO or rc < ZERO or _get(w, "token_balance") < ZERO or _get(w, "credits") < ZERO:
            raise ValueError("EXCHANGE_NEGATIVE_BALANCE")
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
    ]

    if incoming["side"] == "buy":
        candidates = [o for o in candidates
                      if Decimal(str(o["limit_price"])) <= limit]
        candidates.sort(key=lambda o: (Decimal(str(o["limit_price"])), int(o["sequence"])))
    else:
        candidates = [o for o in candidates
                      if Decimal(str(o["limit_price"])) >= limit]
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
        _set_reserve(buyer, "exchange_reserved_credits",
                     _reserve(buyer, "exchange_reserved_credits") - take * bid)
        _set_reserve(seller, "exchange_reserved_slh",
                     _reserve(seller, "exchange_reserved_slh") - take)
        buy["reserved_credits"] = _s(buy_res - take * bid)
        buy["remaining_amount"] = _s(Decimal(str(buy["remaining_amount"])) - take)
        sell["reserved_slh"] = _s(sell_res - take)
        sell["remaining_amount"] = _s(Decimal(str(sell["remaining_amount"])) - take)

        seller_before = _get(seller, "credits")
        _set(seller, "credits", seller_before + cost)
        _ledger(db, seller_uid, seller_before, cost, "exchange:settlement_credits",
                {"trade_id": tid, "order_id": sell["id"]})

        buyer_before = _get(buyer, "token_balance")
        _set(buyer, "token_balance", buyer_before + take)
        _ledger(db, buyer_uid, buyer_before, take, "exchange:settlement_slh",
                {"trade_id": tid, "order_id": buy["id"]})

        improvement = take * (bid - price)
        if improvement > ZERO:
            before = _get(buyer, "credits")
            _set(buyer, "credits", before + improvement)
            _ledger(db, buyer_uid, before, improvement,
                    "exchange:price_improvement_release",
                    {"trade_id": tid, "order_id": buy["id"]})

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


def _place(db, uid, side, amount, price, request_id):
    w = _wallet(db, uid)
    if side == "sell":
        available = _get(w, "token_balance")
        if available < amount:
            raise ValueError("INSUFFICIENT_SLH")
        _set(w, "token_balance", available - amount)
        _set_reserve(w, "exchange_reserved_slh",
                     _reserve(w, "exchange_reserved_slh") + amount)
    else:
        reserve = amount * price
        available = _get(w, "credits")
        if available < reserve:
            raise ValueError("INSUFFICIENT_CREDITS")
        _set(w, "credits", available - reserve)
        _set_reserve(w, "exchange_reserved_credits",
                     _reserve(w, "exchange_reserved_credits") + reserve)

    order = _new_order(db, uid, side, amount, price, request_id)
    if side == "sell":
        _ledger(db, uid, available, -amount, "exchange:sell_reserve",
                {"order_id": order["id"], "request_id": request_id})
    else:
        _ledger(db, uid, available, -amount * price, "exchange:buy_reserve",
                {"order_id": order["id"], "request_id": request_id})

    filled, remaining = _match(db, order)
    result = {
        "order_id": order["id"], "filled": _s(filled), "remaining": _s(remaining),
        "status": order["status"],
    }
    db.setdefault(REQUESTS_KEY, {})[request_id] = result
    _assert_invariants(db)
    return result


def register(bot):
    @bot.message_handler(commands=["sell_slh"])
    def sell_slh(msg):
        parts = msg.text.split()
        if len(parts) != 3:
            bot.reply_to(msg, "שימוש: /sell_slh <amount_slh> <price_in_credits>")
            return
        try:
            amount, price = _dec(parts[1], "amount"), _dec(parts[2], "price")
            uid, key = str(msg.from_user.id), _request_key(msg.from_user.id, msg.message_id)

            def mutate(db):
                old = db.setdefault(REQUESTS_KEY, {}).get(key)
                return old if old is not None else _place(db, uid, "sell", amount, price, key)

            r = state_manager.atomic_update(mutate)
            bot.reply_to(msg, f"✅ SELL #{r['order_id']} | filled {r['filled']} | open {r['remaining']} SLH")
        except ValueError as e:
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

            def mutate(db):
                old = db.setdefault(REQUESTS_KEY, {}).get(key)
                return old if old is not None else _place(db, uid, "buy", amount, price, key)

            r = state_manager.atomic_update(mutate)
            bot.reply_to(msg, f"✅ BUY #{r['order_id']} | filled {r['filled']} | open {r['remaining']} SLH")
        except ValueError as e:
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
                _set_reserve(w, "exchange_reserved_slh",
                             _reserve(w, "exchange_reserved_slh") - res)
                before = _get(w, "token_balance")
                _set(w, "token_balance", before + res)
                _ledger(db, uid, before, res, "exchange:cancel_release_slh", {"order_id": oid})
                o["reserved_slh"] = _s(ZERO)
            else:
                res = Decimal(str(o["reserved_credits"]))
                expected = rem * Decimal(str(o["limit_price"]))
                if res != expected:
                    raise ValueError("ORDER_RESERVE_MISMATCH")
                _set_reserve(w, "exchange_reserved_credits",
                             _reserve(w, "exchange_reserved_credits") - res)
                before = _get(w, "credits")
                _set(w, "credits", before + res)
                _ledger(db, uid, before, res, "exchange:cancel_release_credits", {"order_id": oid})
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
