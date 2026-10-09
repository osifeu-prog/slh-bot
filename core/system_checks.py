"""Canonical read-only system checks for SLH OS.

These checks inspect existing sources of truth only. They never write DB state,
change balances, open settlement gates, sign transactions, or broadcast.
"""

from __future__ import annotations

import json
import os
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


REQUIRED_DB_KEYS = ("users", "transactions", "ledger")
REQUIRED_UX_IDS = ("balance", "move", "growth", "investor", "profile", "bh", "bb", "bm", "bg", "binv")


def check_db() -> dict[str, Any]:
    try:
        import state_manager

        db = state_manager.load_db()
        missing = [key for key in REQUIRED_DB_KEYS if key not in db]
        if missing:
            return {"ok": False, "detail": "missing keys: " + ", ".join(missing)}
        users = db.get("users")
        return {
            "ok": isinstance(users, dict),
            "detail": f"state/db.json readable · users={len(users) if isinstance(users, dict) else 0}",
        }
    except Exception as exc:
        return {"ok": False, "detail": f"state/db.json unreadable: {type(exc).__name__}"}


def check_commands() -> dict[str, Any]:
    try:
        from core.runtime_command_evidence import snapshot_runtime

        snapshot = snapshot_runtime("Me_ad_main")
        collisions = int(snapshot.get("collision_count") or 0)
        required = {"help", "check", "check_ux", "check_money", "check_bnb", "check_ton", "check_exchange"}
        registered = set(snapshot.get("commands", {}))
        missing = sorted("/" + cmd for cmd in required if "/" + cmd not in registered)
        ok = collisions == 0 and not missing
        detail = (
            f"handlers={snapshot.get('total_message_handlers')} "
            f"commands={snapshot.get('unique_commands')} collisions={collisions}"
        )
        if missing:
            detail += " · missing=" + ", ".join(missing)
        return {
            "ok": ok,
            "detail": detail,
            "collisions": collisions,
            "missing": missing,
        }
    except KeyError:
        return {"ok": False, "detail": "runtime bot Me_ad_main is not registered"}
    except Exception as exc:
        return {"ok": False, "detail": f"runtime command snapshot failed: {type(exc).__name__}"}


def check_ux() -> dict[str, Any]:
    try:
        html = Path("mini_app.html").read_text(encoding="utf-8")
        checks = []
        for item in REQUIRED_UX_IDS:
            marker = f'id="{item}"'
            checks.append({"name": marker, "ok": marker in html})
        required_text = (
            "Home",
            "Balance",
            "Move",
            "Grow",
            "Investor",
            "SLH · פנימי",
            "SLH · on-chain",
        )
        for item in required_text:
            checks.append({"name": item, "ok": item in html})
        ok = all(item["ok"] for item in checks)
        return {
            "ok": ok,
            "detail": "Mini App public shell contract present" if ok else "Mini App shell contract incomplete",
            "checks": checks,
        }
    except Exception as exc:
        return {"ok": False, "detail": f"Mini App source check failed: {type(exc).__name__}", "checks": []}



def _decimal(value: Any, default: str = "0") -> Decimal:
    try:
        return Decimal(str(default if value is None else value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("NaN")


def check_exchange(db: dict[str, Any] | None = None, *, for_execution: bool = False) -> dict[str, Any]:
    """Read-only production-state inspection for the internal exchange."""
    try:
        import state_manager
        from core.exchange_gate import public_open
        from core.exchange_housekeeping import is_test_seed
        from handlers.exchange_handler import _assert_invariants

        if db is None:
            db = state_manager.load_db()
        orders = db.get("exchange_orders", {})
        trades = db.get("exchange_trades", [])
        requests = db.get("exchange_requests", {})

        if not isinstance(orders, dict):
            return {
                "ok": False,
                "detail": "exchange_orders is not a dict",
                "open_orders": 0,
                "test_seed_open": 0,
                "recent_trades": 0,
                "test_seed_trades": 0,
                "order_book_integrity": False,
                "trade_integrity": False,
                "money_invariants": False,
                "public_gate": "CLOSED",
                "public_ready": False,
                "verdict": "BLOCKED",
            }
        if not isinstance(trades, list):
            return {
                "ok": False,
                "detail": "exchange_trades is not a list",
                "open_orders": 0,
                "test_seed_open": 0,
                "recent_trades": 0,
                "test_seed_trades": 0,
                "order_book_integrity": False,
                "trade_integrity": False,
                "money_invariants": False,
                "public_gate": "CLOSED",
                "public_ready": False,
                "verdict": "BLOCKED",
            }

        open_orders = [o for o in orders.values() if isinstance(o, dict) and o.get("status") == "open"]
        test_seed_open = [o for o in open_orders if is_test_seed(o)]
        recent_trades = trades[-10:]
        test_seed_trades = [t for t in trades if is_test_seed(t)]

        order_errors = []
        seen_order_ids = set()
        valid_statuses = {"open", "filled", "cancelled"}
        for key, order in orders.items():
            if not isinstance(order, dict):
                order_errors.append(f"order:{key}:not_dict")
                continue
            oid = str(order.get("id", ""))
            if not oid or oid in seen_order_ids or oid != str(key):
                order_errors.append(f"order:{key}:bad_id")
            seen_order_ids.add(oid)

            side = str(order.get("side", ""))
            status = str(order.get("status", ""))
            original = _decimal(order.get("original_amount"))
            remaining = _decimal(order.get("remaining_amount"))
            price = _decimal(order.get("limit_price"))
            if side not in {"buy", "sell"}:
                order_errors.append(f"order:{oid}:bad_side")
            if status not in valid_statuses:
                order_errors.append(f"order:{oid}:bad_status")
            if not original.is_finite() or original <= 0:
                order_errors.append(f"order:{oid}:bad_original")
            if not remaining.is_finite() or remaining < 0 or (original.is_finite() and remaining > original):
                order_errors.append(f"order:{oid}:bad_remaining")
            if not price.is_finite() or price <= 0:
                order_errors.append(f"order:{oid}:bad_price")

            reserved_slh = _decimal(order.get("reserved_slh"))
            reserved_credits = _decimal(order.get("reserved_credits"))
            if status == "open":
                if remaining <= 0:
                    order_errors.append(f"order:{oid}:open_without_remaining")
                if side == "sell" and reserved_slh != remaining:
                    order_errors.append(f"order:{oid}:sell_reserve_mismatch")
                if side == "buy" and reserved_credits != (remaining * price):
                    order_errors.append(f"order:{oid}:buy_reserve_mismatch")
            elif remaining != 0:
                order_errors.append(f"order:{oid}:closed_with_remaining")
            if status != "open" and ((reserved_slh.is_finite() and reserved_slh != 0) or (reserved_credits.is_finite() and reserved_credits != 0)):
                order_errors.append(f"order:{oid}:closed_with_reserve")

        trade_errors = []
        seen_trade_ids = set()
        for trade in trades:
            if not isinstance(trade, dict):
                trade_errors.append("trade:not_dict")
                continue
            tid = str(trade.get("id", ""))
            if not tid or tid in seen_trade_ids:
                trade_errors.append(f"trade:{tid}:duplicate_or_missing_id")
            seen_trade_ids.add(tid)

            amount = _decimal(trade.get("slh_amount"))
            price = _decimal(trade.get("price"))
            value = _decimal(trade.get("credits_value"))
            buyer_uid = str(trade.get("buyer_uid", ""))
            seller_uid = str(trade.get("seller_uid", ""))
            if not amount.is_finite() or amount <= 0:
                trade_errors.append(f"trade:{tid}:bad_amount")
            if not price.is_finite() or price <= 0:
                trade_errors.append(f"trade:{tid}:bad_price")
            if not value.is_finite() or value <= 0 or value != (amount * price):
                trade_errors.append(f"trade:{tid}:bad_value")
            if not buyer_uid or not seller_uid or buyer_uid == seller_uid:
                trade_errors.append(f"trade:{tid}:bad_counterparties")

            buy_order = orders.get(str(trade.get("buy_order_id")))
            sell_order = orders.get(str(trade.get("sell_order_id")))
            if not isinstance(buy_order, dict) or buy_order.get("side") != "buy":
                trade_errors.append(f"trade:{tid}:bad_buy_order")
            if not isinstance(sell_order, dict) or sell_order.get("side") != "sell":
                trade_errors.append(f"trade:{tid}:bad_sell_order")

        try:
            _assert_invariants(db)
            money_ok = True
            money_detail = "PASS"
        except Exception as exc:
            money_ok = False
            money_detail = type(exc).__name__

        order_ok = not order_errors
        trade_ok = not trade_errors
        requests_ok = isinstance(requests, dict)
        clean_for_public = (
            order_ok
            and trade_ok
            and money_ok
            and requests_ok
            and (for_execution or len(open_orders) == 0)
            and len(test_seed_open) == 0
            and len(test_seed_trades) == 0
        )
        gate = "OPEN" if public_open() else "CLOSED"
        verdict = "OPEN" if clean_for_public and gate == "OPEN" else "READY_TO_OPEN" if clean_for_public else "BLOCKED"

        details = []
        if not requests_ok:
            details.append("exchange_requests is not a dict")
        if order_errors:
            details.append("order_book=" + ",".join(order_errors[:5]))
        if trade_errors:
            details.append("trades=" + ",".join(trade_errors[:5]))
        if not money_ok:
            details.append("money=" + money_detail)
        if len(open_orders) and not for_execution:
            details.append(f"open_orders={len(open_orders)}")
        elif len(open_orders):
            details.append(f"live_open_orders={len(open_orders)}")
        if len(test_seed_trades):
            details.append(f"test_seed_trades={len(test_seed_trades)}")
        detail = "public state clean" if not details else " · ".join(details)

        public_ready = bool(clean_for_public)
        ok = order_ok and trade_ok and money_ok and requests_ok
        return {
            "ok": ok,
            "detail": detail,
            "open_orders": len(open_orders),
            "test_seed_open": len(test_seed_open),
            "recent_trades": len(recent_trades),
            "test_seed_trades": len(test_seed_trades),
            "order_book_integrity": order_ok,
            "trade_integrity": trade_ok,
            "money_invariants": money_ok,
            "public_gate": gate,
            "public_ready": public_ready,
            "verdict": verdict,
        }
    except Exception as exc:
        return {
            "ok": False,
            "detail": f"exchange read-only check failed: {type(exc).__name__}",
            "open_orders": 0,
            "test_seed_open": 0,
            "recent_trades": 0,
            "test_seed_trades": 0,
            "order_book_integrity": False,
            "trade_integrity": False,
            "money_invariants": False,
            "public_gate": "CLOSED",
            "public_ready": False,
            "verdict": "BLOCKED",
        }



def check_exchange_for_execution(db: dict[str, Any]) -> dict[str, Any]:
    """Fresh fail-closed exchange check against the exact state being mutated.

    Unlike launch-readiness, execution readiness allows valid live customer
    orders to remain in the book. Test/seed orders, invalid trades, broken
    reserves, a closed public gate, or any failed invariant still block entry.
    """
    result = check_exchange(db, for_execution=True)
    ready = (
        bool(result.get("ok"))
        and bool(result.get("public_ready"))
        and bool(result.get("order_book_integrity"))
        and bool(result.get("trade_integrity"))
        and bool(result.get("money_invariants"))
        and str(result.get("public_gate")) == "OPEN"
        and str(result.get("verdict")) == "OPEN"
    )
    result["execution_ready"] = ready
    result["ok"] = ready
    if not ready:
        result["verdict"] = "BLOCKED"
        if str(result.get("public_gate")) != "OPEN":
            result["detail"] = "public exchange gate is CLOSED"
        elif not result.get("detail") or result.get("detail") == "public state clean":
            result["detail"] = "fresh execution check blocked"
    return result

def check_money(uid: str) -> dict[str, Any]:
    checks = []
    try:
        from core import economy_service

        balance = economy_service.get_balance_safe(uid)
        staked = economy_service.get_staked_safe(uid)
        checks.append({"name": f"Credits readable ({balance})", "ok": True, "detail": ""})
        checks.append({"name": f"Staked readable ({staked})", "ok": True, "detail": ""})
    except Exception as exc:
        checks.append({"name": "Economy read", "ok": False, "detail": type(exc).__name__})

    try:
        from handlers.exchange_handler import _assert_invariants
        import state_manager

        _assert_invariants(state_manager.load_db())
        checks.append({"name": "Exchange reserve invariants", "ok": True, "detail": ""})
    except Exception as exc:
        checks.append({"name": "Exchange reserve invariants", "ok": False, "detail": type(exc).__name__})

    try:
        from core.revenue_ledger import summary

        data = summary()
        checks.append(
            {"name": f"Revenue ledger readable ({int(data.get('events', 0))} events)", "ok": True, "detail": ""}
        )
    except Exception as exc:
        checks.append({"name": "Revenue ledger", "ok": False, "detail": type(exc).__name__})

    ok = all(item["ok"] for item in checks)
    return {
        "ok": ok,
        "detail": "internal financial reads/invariants PASS" if ok else "one or more financial read checks failed",
        "checks": checks,
    }


def check_bnb() -> dict[str, Any]:
    """Report BNB go-live truth, not merely configuration readiness."""
    try:
        from core.bnb_gate import bnb_deposits_open, bnb_opening_evidence, bnb_readiness

        gate = bnb_readiness()
        evidence = bnb_opening_evidence()
        empirical = evidence.get("empirical_settlement") or {}
        empirical_status = str(empirical.get("status") or "PENDING_EMPIRICAL")
        configuration_ready = bool(gate.get("ready")) and not bool(evidence.get("blockers"))
        launch_ready = bool(evidence.get("ready_to_open"))
        flag_open = bool(gate.get("flag_open"))
        public_open = bool(bnb_deposits_open())

        # Go-live is green only if runtime settlement is actually open and the
        # persisted proof has been revalidated against live chain + ledger.
        ok = (
            public_open
            and flag_open
            and configuration_ready
            and launch_ready
            and empirical_status == "PASS"
        )
        if ok:
            detail = "BNB gate OPEN; empirical settlement proof revalidated against live chain and ledger"
        elif flag_open and not public_open:
            detail = "BNB_DEPOSITS_OPEN=1 but live empirical evidence is not valid; runtime gate remains CLOSED"
        elif not flag_open and launch_ready:
            detail = "BNB empirical proof revalidated; public gate remains CLOSED pending operator opening"
        elif configuration_ready:
            detail = "BNB gate CLOSED safely; configuration ready but empirical settlement proof pending/invalid"
        else:
            detail = "BNB readiness requires attention"

        return {
            "ok": ok,
            "detail": detail,
            "public_open": public_open,
            "flag_open": flag_open,
            "ready": configuration_ready,
            "launch_ready": launch_ready,
            "empirical_status": empirical_status,
            "confirmations_required": gate.get("confirmations_required"),
            "blockers": evidence.get("blockers", []),
        }
    except Exception as exc:
        return {
            "ok": False,
            "detail": f"BNB read-only check failed: {type(exc).__name__}",
            "public_open": False,
            "flag_open": False,
            "ready": False,
            "launch_ready": False,
            "empirical_status": "UNKNOWN",
            "confirmations_required": 0,
        }


def check_ton(uid: str) -> dict[str, Any]:
    try:
        from core.ton_deposit_service import ton_readiness
        import state_manager

        readiness = ton_readiness()
        db = state_manager.load_db()
        replay = db.get("ton_replay_evidence", {}) if isinstance(db, dict) else {}
        user_replay = replay.get(str(uid)) if isinstance(replay, dict) else None
        replay_label = "present" if isinstance(user_replay, dict) else "not recorded for this UID"
        ok = bool(readiness.get("ready")) and bool(readiness.get("effective_open"))
        detail = "TON public gate OPEN and readiness valid" if ok else "TON readiness/gate requires attention"
        return {
            "ok": ok,
            "detail": detail,
            "public_open": bool(readiness.get("effective_open")),
            "ready": bool(readiness.get("ready")),
            "rate": readiness.get("rate") or "0",
            "replay_evidence": replay_label,
        }
    except Exception as exc:
        return {
            "ok": False,
            "detail": f"TON read-only check failed: {type(exc).__name__}",
            "public_open": False,
            "ready": False,
            "rate": "0",
            "replay_evidence": "unknown",
        }
