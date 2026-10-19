"""Read-only SLH exchange reserve reconciliation.

This module reports discrepancies only. It never mutates balances, orders,
ledgers, freezes, or exchange gates.
"""
from __future__ import annotations

from collections import Counter
import json
from decimal import Decimal, InvalidOperation
from datetime import datetime, date
import os
import time

import state_manager


# These findings represent unresolved financial dispositions. They remain
# launch blockers even if the underlying order has been archived or classified
# as a historical test seed; archive metadata is not accounting authorization.
RELEASE_GATE_BLOCKER_CODES = frozenset({
    "CANCELLED_SELL_ORDER_MISSING_NORMAL_RELEASE",
    "RESERVE_DELTA_NOT_ZERO",
    "MANUAL_RESERVE_CORRECTION_REQUIRES_REVIEW",
    "ORPHAN_RESERVE_CORRECTION",
    "INVALID_RESERVE_LEDGER_AMOUNT",
    "LEDGER_EVENT_ID_MISSING",
    "DUPLICATE_LEDGER_EVENT_ID",
    "CROSS_LEDGER_EVENT_ID_REQUIRES_REVIEW",
    "MIXED_LEDGER_DOMAINS_REQUIRES_REVIEW",
    "ARCHIVED_TRADE_ID_INVALID",
    "ARCHIVED_TRADE_ORDER_LINK_INVALID",
    "ARCHIVED_TRADE_PARTY_MISMATCH",
    "ARCHIVED_TRADE_VALUE_INVALID",
    "ARCHIVED_TRADE_PRICE_OUTSIDE_LIMITS",
    "ARCHIVED_TRADE_PRICE_EVIDENCE_INVALID",
    "ARCHIVED_TRADE_ARCHIVE_UNREADABLE",
})

# Event IDs became mandatory on 2026-09-28. Earlier ordinary reserve/release
# rows cannot be retroactively stamped; their accounting still must reconcile.
EVENT_ID_ERA_START = date.fromisoformat("2026-09-28")


def _predates_event_id_requirement(event):
    """Return True only for a valid timestamp strictly before event-ID policy.

    Missing or malformed timestamps fail closed. This suppresses only a
    metadata-only finding for a known order's ordinary reserve/release row;
    it does not suppress reserve deltas, orphan corrections, or other findings.
    """
    if not isinstance(event, dict):
        return False
    raw = str(event.get("time") or "").strip()
    if not raw:
        return False
    try:
        normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
        stamped = datetime.fromisoformat(normalized)
    except (TypeError, ValueError, OverflowError):
        return False
    return stamped.date() < EVENT_ID_ERA_START

def _records(value):
    if isinstance(value, dict):
        return [(str(key), item) for key, item in value.items() if isinstance(item, dict)]
    if isinstance(value, list):
        return [(str(item.get("id", index)), item) for index, item in enumerate(value) if isinstance(item, dict)]
    return []


def _amount(value):
    if value is None or value == "":
        return None
    try:
        amount = Decimal(str(value))
        return amount if amount.is_finite() else None
    except (InvalidOperation, ValueError, TypeError):
        return None


def _ledger_delta(event, amount, group, ledger_name):
    """Normalize reserve/release sign inside one ledger's own accounting domain.

    The Credits ledger uses signed deltas. The SLH token ledger stores positive
    magnitudes and identifies direction with kind=exchange_reserve/release.
    Callers must never add deltas from the two ledgers together.
    """
    if ledger_name == "slh_token_ledger":
        kind = str(event.get("kind") or "").strip().lower()
        if group == "reserve" and kind == "exchange_reserve":
            return -abs(amount)
        if group == "normal_release" and kind == "exchange_release":
            return abs(amount)
    return amount


def audit_db(db):
    """Return a read-only reserve report with ledger domains kept separate."""
    findings = []
    orders = {}
    order_source_by_id = {}
    for key, order in _records(db.get("exchange_orders", {})):
        oid = str(order.get("order_id") or order.get("id") or key)
        orders[oid] = order
        order_source_by_id[oid] = "active"
    for key, order in _records(db.get("exchange_order_archive", {})):
        oid = str(order.get("order_id") or order.get("id") or key)
        orders[oid] = order
        order_source_by_id[oid] = "archive"

    sources = (
        ("ledger", _records(db.get("ledger", []))),
        ("slh_token_ledger", _records(db.get("slh_token_ledger", []))),
    )
    known_order_ids = set(orders)

    def _uid(order):
        return str(order.get("uid") or order.get("user_id") or "")

    # Archived trades remain part of financial history. Archival metadata must
    # not make an invalid trade/order relationship disappear from release checks.
    seen_archived_trade_ids = set()
    archived_trade_source = db.get("exchange_trade_archive", [])
    if "exchange_trade_archive" in db:
        malformed_archive = (
            not isinstance(archived_trade_source, (dict, list))
            or (
                isinstance(archived_trade_source, list)
                and any(not isinstance(item, dict) for item in archived_trade_source)
            )
            or (
                isinstance(archived_trade_source, dict)
                and any(not isinstance(item, dict) for item in archived_trade_source.values())
            )
        )
        if malformed_archive:
            findings.append({"code": "ARCHIVED_TRADE_ARCHIVE_UNREADABLE"})
    for key, trade in _records(archived_trade_source):
        raw_tid = trade.get("trade_id") or trade.get("id")
        tid = str(raw_tid or "").strip()
        buy_id = str(trade.get("buy_order_id") or "").strip()
        sell_id = str(trade.get("sell_order_id") or "").strip()
        linked_order_ids = sorted({oid for oid in (buy_id, sell_id) if oid})

        if not tid or tid in seen_archived_trade_ids:
            findings.append({
                "code": "ARCHIVED_TRADE_ID_INVALID",
                "trade_id": tid or str(key),
                "order_ids": linked_order_ids,
            })
        if tid:
            seen_archived_trade_ids.add(tid)

        buy_order = orders.get(buy_id) if buy_id else None
        sell_order = orders.get(sell_id) if sell_id else None
        buy_ok = isinstance(buy_order, dict) and str(buy_order.get("side") or "").lower() == "buy"
        sell_ok = isinstance(sell_order, dict) and str(sell_order.get("side") or "").lower() == "sell"
        if not buy_id or not sell_id or buy_id == sell_id or not buy_ok or not sell_ok:
            findings.append({
                "code": "ARCHIVED_TRADE_ORDER_LINK_INVALID",
                "trade_id": tid or str(key),
                "order_ids": linked_order_ids,
            })
            continue

        buyer_uid = str(trade.get("buyer_uid") or "")
        seller_uid = str(trade.get("seller_uid") or "")
        if (
            not buyer_uid or not seller_uid or buyer_uid == seller_uid
            or _uid(buy_order) != buyer_uid
            or _uid(sell_order) != seller_uid
        ):
            findings.append({
                "code": "ARCHIVED_TRADE_PARTY_MISMATCH",
                "trade_id": tid or str(key),
                "order_ids": linked_order_ids,
            })

        amount = _amount(trade.get("slh_amount"))
        price = _amount(trade.get("price"))
        value = _amount(trade.get("credits_value"))
        if (
            amount is None or amount <= 0
            or price is None or price <= 0
            or value is None or value <= 0
            or value != amount * price
        ):
            findings.append({
                "code": "ARCHIVED_TRADE_VALUE_INVALID",
                "trade_id": tid or str(key),
                "order_ids": linked_order_ids,
            })

        bid = _amount(buy_order.get("limit_price"))
        ask = _amount(sell_order.get("limit_price"))
        if bid is None or ask is None or price is None:
            findings.append({
                "code": "ARCHIVED_TRADE_PRICE_EVIDENCE_INVALID",
                "trade_id": tid or str(key),
                "order_ids": linked_order_ids,
            })
        elif price > bid or price < ask:
            findings.append({
                "code": "ARCHIVED_TRADE_PRICE_OUTSIDE_LIMITS",
                "trade_id": tid or str(key),
                "order_ids": linked_order_ids,
            })

    # Cache expected current reserves per account. Values are never emitted in
    # findings; only consistency booleans are added for safe operator triage.
    open_sell_reserve_by_uid = {}
    open_sell_reserve_unknown_uids = set()
    for oid, order in orders.items():
        if order_source_by_id.get(oid) != "active":
            continue
        if str(order.get("side") or "").lower() != "sell" or str(order.get("status") or "").lower() != "open":
            continue
        uid = _uid(order)
        if not uid:
            continue
        amount = _amount(order.get("reserved_slh"))
        if amount is None:
            open_sell_reserve_unknown_uids.add(uid)
            continue
        open_sell_reserve_by_uid[uid] = open_sell_reserve_by_uid.get(uid, Decimal(0)) + amount

    def _current_order_context(order_id):
        oid = str(order_id or "")
        order = orders.get(oid)
        if not isinstance(order, dict):
            return {}
        uid = _uid(order)
        users = db.get("users", {})
        user = users.get(uid) if uid and isinstance(users, dict) else None
        wallet = user.get("wallet") if isinstance(user, dict) else None
        wallet = wallet if isinstance(wallet, dict) else {}
        remaining = _amount(order.get("remaining_amount"))
        order_reserve = _amount(order.get("reserved_slh"))
        wallet_reserve = (
            _amount(wallet.get("exchange_reserved_slh", 0))
            if isinstance(user, dict) else None
        )
        expected_open_reserve = open_sell_reserve_by_uid.get(uid, Decimal(0))
        reserve_match = (
            wallet_reserve == expected_open_reserve
            if uid and wallet_reserve is not None and uid not in open_sell_reserve_unknown_uids
            else None
        )
        try:
            from core.exchange_housekeeping import is_test_seed
            # Archive metadata is assigned by the archiver itself. In particular,
            # archive_reason="test_seed_retirement" must not prove that the
            # pre-archive record was a seed; exclude bookkeeping fields and
            # require independent seed evidence in the preserved order payload.
            seed_evidence_order = {
                key: value for key, value in order.items()
                if key not in {"archive_reason", "archived_at", "archived_by"}
            }
            test_seed = bool(is_test_seed(seed_evidence_order))
        except Exception:
            # Classification is diagnostic only; never allow it to affect audit status.
            test_seed = None
        archived = order_source_by_id.get(oid) == "archive"
        return {
            "order_status": str(order.get("status") or "UNKNOWN").upper(),
            "order_remaining_is_zero": remaining == 0 if remaining is not None else None,
            "order_reserved_slh_is_zero": order_reserve == 0 if order_reserve is not None else None,
            "wallet_reserved_slh_is_zero": wallet_reserve == 0 if wallet_reserve is not None else None,
            "wallet_reserve_matches_open_orders": reserve_match,
            "order_is_archived": archived,
            "order_is_test_seed": test_seed,
            "order_is_archived_test_seed": archived and test_seed is True and str(order.get("archive_reason") or "") == "test_seed_retirement",
        }


    def _meta(event):
        value = event.get("meta")
        return value if isinstance(value, dict) else {}

    def _event_id(event):
        value = event.get("event_id") or _meta(event).get("event_id")
        return str(value).strip() if value is not None and str(value).strip() else ""

    def _order_id(event):
        return str(event.get("order_id") or _meta(event).get("order_id") or "")

    def _event_groups(event):
        reason = str(event.get("reason") or "").lower()
        kind = str(event.get("kind") or "").lower()
        correction = "correction" in reason or "correction" in kind
        reserve = (
            "sell_reserve" in reason
            or "sell_reserve" in kind
            or kind == "exchange_reserve"
        )
        release = (
            ("release" in reason or "release" in kind)
            and not correction
        )
        return reserve, release, correction

    def _is_exchange_audit_event(event):
        reserve, release, correction = _event_groups(event)
        reason = str(event.get("reason") or "").lower()
        kind = str(event.get("kind") or "").lower()
        order_id = _order_id(event)

        if reserve:
            return True

        # BUY-order cancellation releases Credits, not SLH. This audit is
        # intentionally limited to SLH SELL reserves; counting a Credits release
        # here creates a false missing-event-ID finding for unrelated BUY orders.
        if "credits" in reason or "credits" in kind:
            return False
        order = orders.get(order_id)
        if isinstance(order, dict) and str(order.get("side") or "").lower() == "buy":
            return False

        if correction:
            # The general ledger also contains non-exchange corrections.
            # Only include corrections evidenced as exchange/reserve-specific,
            # or explicitly attached to a known SELL order.
            event_id = _event_id(event).lower()
            evidence = " ".join((reason, kind, event_id))
            reserve_correction = any(
                marker in evidence
                for marker in ("exchange", "reserve", "missed_release")
            )
            return order_id in known_order_ids or reserve_correction

        if not release:
            return False
        return (
            order_id in known_order_ids
            or reason in {"exchange:cancel_release", "exchange:cancel_release_slh"}
            or kind in {"exchange_release"}
        )

    def _verified_missed_release_correction(order_id):
        """Recognize only the exact mirrored legacy correction written by
        correct_missed_release() for an unfilled archived test-seed order.

        A correction is reconciled only when both ledgers contain the same
        unique event, amounts and balance snapshots form one consistent
        reserve-and-restore cycle, the source writer's SLH metadata is present,
        the current wallet is still the legacy model, and the token-ledger
        balance chain reaches the current wallet balance. Otherwise fail closed.
        """
        oid = str(order_id or "")
        order = orders.get(oid)
        if (
            not oid
            or not isinstance(order, dict)
            or order_source_by_id.get(oid) != "archive"
        ):
            return False
        context = _current_order_context(oid)
        if (
            context.get("order_is_archived_test_seed") is not True
            or context.get("order_status") != "CANCELLED"
            or context.get("order_remaining_is_zero") is not True
            or context.get("order_reserved_slh_is_zero") is not True
            or context.get("wallet_reserve_matches_open_orders") is not True
            or str(order.get("side") or "").lower() != "sell"
        ):
            return False

        uid = _uid(order)
        users = db.get("users", {})
        user = users.get(uid) if uid and isinstance(users, dict) else None
        wallet = user.get("wallet") if isinstance(user, dict) else None
        if not isinstance(wallet, dict) or wallet.get("live_token_balance") is not None:
            return False
        current_token_balance = _amount(wallet.get("token_balance"))
        original = _amount(order.get("original_amount"))
        if current_token_balance is None or original is None or original <= 0:
            return False

        # This exception is deliberately limited to an unfilled order. Filled
        # orders need their own trade-settlement evidence and cannot use a
        # cancellation correction to reconcile the sold portion.
        related_trades = []
        for trade_source_name in ("exchange_trades", "exchange_trade_archive"):
            for _, trade in _records(db.get(trade_source_name, [])):
                if str(trade.get("sell_order_id") or "") == oid:
                    related_trades.append(trade)
        if related_trades:
            return False

        source_by_name = dict(sources)
        ledger_source = source_by_name.get("ledger", [])
        token_source = source_by_name.get("slh_token_ledger", [])
        ledger_rows = [event for _, event in ledger_source if _order_id(event) == oid]
        token_rows = [event for _, event in token_source if _order_id(event) == oid]
        expected_event_id = f"correction:missed_release:{oid}"

        reserve_rows = [
            event for event in ledger_rows
            if str(event.get("reason") or "") == "exchange:sell_reserve"
            and str(event.get("uid") or "") == uid
        ]
        ledger_corrections = [
            event for event in ledger_rows
            if str(event.get("reason") or "") == "exchange:missed_release_correction"
        ]
        token_corrections = [
            event for event in token_rows
            if str(event.get("reason") or "") == "exchange:missed_release_correction"
        ]
        token_reserves = [
            event for event in token_rows if _event_groups(event)[0]
        ]
        normal_releases = [
            event for event in ledger_rows + token_rows
            if _event_groups(event)[1] and not _event_groups(event)[2]
        ]
        if (
            len(reserve_rows) != 1
            or len(ledger_corrections) != 1
            or len(token_corrections) != 1
            or token_reserves
            or normal_releases
            or _event_id(ledger_corrections[0]) != expected_event_id
            or _event_id(token_corrections[0]) != expected_event_id
        ):
            return False

        # The event ID must be unique within each ledger. Its intentional
        # cross-ledger pair is validated below rather than blindly deduplicated.
        for source in (ledger_source, token_source):
            if sum(1 for _, event in source if _event_id(event) == expected_event_id) != 1:
                return False

        reserve = reserve_rows[0]
        correction = ledger_corrections[0]
        token_correction = token_corrections[0]
        correction_meta = _meta(correction)
        reserve_before = _amount(reserve.get("before"))
        reserve_after = _amount(reserve.get("after"))
        reserve_delta = _amount(reserve.get("amount"))
        correction_before = _amount(correction.get("before"))
        correction_after = _amount(correction.get("after"))
        correction_amount = _amount(correction.get("amount"))
        token_before = _amount(token_correction.get("before_to"))
        token_after = _amount(token_correction.get("after_to"))
        token_amount = _amount(token_correction.get("amount"))
        operator = str(correction_meta.get("operator_uid") or "").strip()
        token_operator = str(token_correction.get("operator_uid") or "").strip()
        note = str(correction_meta.get("note") or "").strip()
        token_note = str(token_correction.get("note") or "").strip()
        ledger_time = str(correction.get("time") or "").strip()
        token_time = str(token_correction.get("timestamp") or token_correction.get("time") or "").strip()
        reserve_time = str(reserve.get("time") or "").strip()

        if (
            str(correction_meta.get("asset") or "").strip().upper() != "SLH"
            or correction_meta.get("order_id") != oid
            or correction_meta.get("event_id") != expected_event_id
            or str(token_correction.get("kind") or "") != "reserve_release_correction"
            or str(token_correction.get("from_uid") or "") != "__EXCHANGE_RESERVE__"
            or str(token_correction.get("to_uid") or "") != uid
            or str(token_correction.get("order_id") or "") != oid
            or str(correction.get("uid") or "") != uid
            or str(token_correction.get("operator_uid") or "").strip() != operator
            or not operator
            or not note
            or str(token_correction.get("note") or "").strip() != note
            or not ledger_time
            or ledger_time != token_time
            or not reserve_time
            or any(value is None for value in (
                reserve_before, reserve_after, reserve_delta,
                correction_before, correction_after, correction_amount,
                token_before, token_after, token_amount,
            ))
        ):
            return False

        def _aware_time(raw):
            try:
                normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
                parsed = datetime.fromisoformat(normalized)
                return parsed if parsed.tzinfo is not None and parsed.utcoffset() is not None else None
            except (TypeError, ValueError, OverflowError):
                return None

        parsed_reserve_time = _aware_time(reserve_time)
        parsed_correction_time = _aware_time(ledger_time)
        if (
            parsed_reserve_time is None
            or parsed_correction_time is None
            or parsed_reserve_time >= parsed_correction_time
        ):
            return False

        # The legacy reserve and its one-time correction must exactly reverse
        # each other's balance snapshots. No positive/negative amounts from
        # separate accounting domains are netted to make this check pass.
        if not (
            reserve_delta == reserve_after - reserve_before
            and reserve_delta == -original
            and correction_amount == original
            and correction_after - correction_before == correction_amount
            and token_amount == correction_amount
            and token_before == correction_before
            and token_after == correction_after
            and reserve_after == correction_before
            and reserve_before == correction_after
        ):
            return False

        # Prove that the current legacy token_balance is the last balance in
        # the canonical token-ledger chain for this UID after the correction.
        token_correction_index = next(
            (i for i, (_, event) in enumerate(token_source) if event is token_correction),
            None,
        )
        if token_correction_index is None:
            return False
        tail = correction_after
        for _, event in token_source[token_correction_index + 1:]:
            from_uid = str(event.get("from_uid") or "")
            to_uid = str(event.get("to_uid") or "")
            seller_uid = str(event.get("seller_uid") or "")
            if uid not in {from_uid, to_uid, seller_uid}:
                continue
            event_time_raw = str(event.get("timestamp") or event.get("time") or "").strip()
            event_time = _aware_time(event_time_raw)
            if event_time is None or event_time <= parsed_correction_time:
                return False
            if from_uid == uid:
                before_value = _amount(event.get("before_from"))
                after_value = _amount(event.get("after_from"))
            elif to_uid == uid:
                before_value = _amount(event.get("before_to"))
                after_value = _amount(event.get("after_to"))
            else:
                before_value = _amount(event.get("seller_total_before"))
                after_value = _amount(event.get("seller_total_after"))
            if before_value is None or after_value is None or before_value != tail:
                return False
            tail = after_value
        return current_token_balance == tail

    def _verified_legacy_trade_settlement(order_id):
        """Verify one fully filled, pre-canonical archived seed trade.

        This exception is intentionally narrower than an archive classification:
        both archived orders and the one archived trade must agree exactly, and
        the legacy Credits ledger must contain the complete reserve/payout/buyer
        settlement chain with valid arithmetic and timestamps before the canonical
        exchange-settlement migration. Any duplicate, missing row, current-canonical
        counterpart, or contradictory snapshot fails closed.
        """
        oid = str(order_id or "")
        sell_order = orders.get(oid)
        context = _current_order_context(oid)
        if (
            not oid
            or not isinstance(sell_order, dict)
            or order_source_by_id.get(oid) != "archive"
            or context.get("order_is_archived_test_seed") is not True
            or str(sell_order.get("side") or "").lower() != "sell"
            or str(sell_order.get("status") or "").lower()
                not in {"cancelled", "canceled", "closed", "expired"}
            or context.get("order_remaining_is_zero") is not True
            or context.get("order_reserved_slh_is_zero") is not True
            or context.get("wallet_reserve_matches_open_orders") is not True
        ):
            return False

        seller_uid = _uid(sell_order)
        users = db.get("users", {})
        seller_user = users.get(seller_uid) if seller_uid and isinstance(users, dict) else None
        seller_wallet = seller_user.get("wallet") if isinstance(seller_user, dict) else None
        if (
            not isinstance(seller_wallet, dict)
            or seller_wallet.get("live_token_balance") is not None
            or _amount(seller_wallet.get("token_balance")) is None
        ):
            return False

        def _parse_aware_time(raw):
            raw = str(raw or "").strip()
            if not raw:
                return None
            try:
                normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
                parsed = datetime.fromisoformat(normalized)
            except (TypeError, ValueError, OverflowError):
                return None
            return parsed if parsed.tzinfo is not None and parsed.utcoffset() is not None else None

        # This is the source-backed cutover at which exchange SLH settlement
        # moved into core.slh_distribution and slh_token_ledger.
        canonical_migration_at = datetime.fromisoformat("2026-09-22T19:58:16+00:00")

        buy_id = str(sell_order.get("matched_buy_order_id") or "")
        archived_trades = _records(db.get("exchange_trade_archive", []))
        active_trades = _records(db.get("exchange_trades", []))
        matching_sell = [
            (source_name, trade)
            for source_name, source in (
                ("exchange_trades", active_trades),
                ("exchange_trade_archive", archived_trades),
            )
            for _, trade in source
            if str(trade.get("sell_order_id") or "") == oid
        ]
        if len(matching_sell) != 1 or matching_sell[0][0] != "exchange_trade_archive":
            return False
        trade = matching_sell[0][1]

        trade_id = str(trade.get("trade_id") or trade.get("id") or "").strip()
        buy_id = str(trade.get("buy_order_id") or "").strip()
        if not trade_id or not buy_id or buy_id == oid:
            return False

        # IDs must resolve to one archived order each, not a shadow active order.
        def _order_sources_for_id(candidate_id):
            matches = []
            for source_name, source_value in (
                ("exchange_orders", db.get("exchange_orders", {})),
                ("exchange_order_archive", db.get("exchange_order_archive", {})),
            ):
                for key, candidate in _records(source_value):
                    candidate_oid = str(candidate.get("order_id") or candidate.get("id") or key)
                    if candidate_oid == candidate_id:
                        matches.append((source_name, candidate))
            return matches

        sell_source_matches = _order_sources_for_id(oid)
        buy_source_matches = _order_sources_for_id(buy_id)
        if (
            len(sell_source_matches) != 1
            or sell_source_matches[0][0] != "exchange_order_archive"
            or len(buy_source_matches) != 1
            or buy_source_matches[0][0] != "exchange_order_archive"
        ):
            return False

        buy_order = orders.get(buy_id)
        buyer_uid = str(trade.get("buyer_uid") or "")
        if (
            not isinstance(buy_order, dict)
            or str(buy_order.get("side") or "").lower() != "buy"
            or str(buy_order.get("status") or "").lower() == "open"
            or _uid(buy_order) != buyer_uid
            or not buyer_uid
            or buyer_uid == seller_uid
            or _amount(buy_order.get("remaining_amount")) != 0
        ):
            return False
        try:
            from core.exchange_housekeeping import is_test_seed
            buyer_seed_order = {
                key: value for key, value in buy_order.items()
                if key not in {"archive_reason", "archived_at", "archived_by"}
            }
            if not is_test_seed(buyer_seed_order):
                return False
        except Exception:
            return False

        # Exactly one archived trade may account for each fully consumed order.
        matching_buy = [
            (source_name, item)
            for source_name, source in (
                ("exchange_trades", active_trades),
                ("exchange_trade_archive", archived_trades),
            )
            for _, item in source
            if str(item.get("buy_order_id") or "") == buy_id
        ]
        if (
            len(matching_buy) != 1
            or matching_buy[0][0] != "exchange_trade_archive"
            or matching_buy[0][1] is not trade
        ):
            return False

        amount = _amount(trade.get("slh_amount"))
        price = _amount(trade.get("price"))
        credits_value = _amount(trade.get("credits_value"))
        sell_original = _amount(sell_order.get("original_amount"))
        buy_original = _amount(buy_order.get("original_amount"))
        bid = _amount(buy_order.get("limit_price"))
        ask = _amount(sell_order.get("limit_price"))
        trade_time = _parse_aware_time(trade.get("timestamp") or trade.get("time"))
        if (
            amount is None or amount <= 0
            or price is None or price <= 0
            or credits_value is None or credits_value != amount * price
            or sell_original != amount
            or buy_original != amount
            or _amount(sell_order.get("remaining_amount")) != 0
            or _amount(sell_order.get("reserved_slh")) != 0
            or _amount(buy_order.get("reserved_credits", 0)) != 0
            or bid is None or ask is None
            or bid != price or ask != price
            or trade_time is None
            or trade_time >= canonical_migration_at
        ):
            return False

        source_by_name = dict(sources)
        ledger_source = source_by_name.get("ledger", [])
        token_source = source_by_name.get("slh_token_ledger", [])

        # Any canonical token settlement for this trade contradicts the claim
        # that this is a wholly pre-migration legacy settlement.
        canonical_trade_rows = [
            event for _, event in token_source
            if str(event.get("trade_id") or "") == trade_id
            or _event_id(event) == f"exchange:settlement_slh:{trade_id}"
        ]
        if canonical_trade_rows:
            return False

        # There must be one—and only one—SLH reserve row on the legacy ledger,
        # with no release/correction in either ledger for the same sell order.
        order_group_rows = []
        for ledger_name, source in sources:
            for _, event in source:
                if _order_id(event) != oid:
                    continue
                reserve, release, correction = _event_groups(event)
                if reserve or release or correction:
                    order_group_rows.append((ledger_name, event, reserve, release, correction))
        reserve_rows = [
            (ledger_name, event) for ledger_name, event, reserve, _, _ in order_group_rows
            if reserve
        ]
        if (
            len(reserve_rows) != 1
            or reserve_rows[0][0] != "ledger"
            or reserve_rows[0][1].get("reason") != "exchange:sell_reserve"
            or any(release or correction for _, _, _, release, correction in order_group_rows)
        ):
            return False
        reserve = reserve_rows[0][1]
        if str(reserve.get("uid") or "") != seller_uid:
            return False

        def _matches_order(event, expected_order_id):
            return _order_id(event) == expected_order_id

        def _matches_trade(event):
            return str(_meta(event).get("trade_id") or event.get("trade_id") or "") == trade_id

        buy_reserve_rows = [
            event for _, event in ledger_source
            if str(event.get("reason") or "") == "exchange:buy_reserve"
            and _matches_order(event, buy_id)
        ]
        seller_settlement_rows = [
            event for _, event in ledger_source
            if str(event.get("reason") or "") == "exchange:settlement_credits"
            and _matches_trade(event)
        ]
        buyer_settlement_rows = [
            event for _, event in ledger_source
            if str(event.get("reason") or "") == "exchange:settlement_slh"
            and _matches_trade(event)
        ]
        if (
            len(buy_reserve_rows) != 1
            or len(seller_settlement_rows) != 1
            or len(buyer_settlement_rows) != 1
        ):
            return False
        buy_reserve = buy_reserve_rows[0]
        seller_settlement = seller_settlement_rows[0]
        buyer_settlement = buyer_settlement_rows[0]
        if (
            str(buy_reserve.get("uid") or "") != buyer_uid
            or str(seller_settlement.get("uid") or "") != seller_uid
            or str(buyer_settlement.get("uid") or "") != buyer_uid
            or not _matches_order(seller_settlement, oid)
            or not _matches_order(buyer_settlement, buy_id)
            or any(_event_id(event) for event in (
                reserve, buy_reserve, seller_settlement, buyer_settlement
            ))
        ):
            return False

        reserve_before = _amount(reserve.get("before"))
        reserve_amount = _amount(reserve.get("amount"))
        reserve_after = _amount(reserve.get("after"))
        buy_before = _amount(buy_reserve.get("before"))
        buy_amount = _amount(buy_reserve.get("amount"))
        buy_after = _amount(buy_reserve.get("after"))
        seller_before = _amount(seller_settlement.get("before"))
        seller_amount = _amount(seller_settlement.get("amount"))
        seller_after = _amount(seller_settlement.get("after"))
        buyer_before = _amount(buyer_settlement.get("before"))
        buyer_amount = _amount(buyer_settlement.get("amount"))
        buyer_after = _amount(buyer_settlement.get("after"))
        if any(value is None for value in (
            reserve_before, reserve_amount, reserve_after,
            buy_before, buy_amount, buy_after,
            seller_before, seller_amount, seller_after,
            buyer_before, buyer_amount, buyer_after,
        )):
            return False
        if not (
            reserve_before + reserve_amount == reserve_after
            and reserve_amount == -amount
            and buy_before + buy_amount == buy_after
            and buy_amount == -credits_value
            and seller_before + seller_amount == seller_after
            and seller_amount == credits_value
            and buyer_before + buyer_amount == buyer_after
            and buyer_amount == amount
        ):
            return False

        reserve_time = _parse_aware_time(reserve.get("time"))
        buy_reserve_time = _parse_aware_time(buy_reserve.get("time"))
        seller_settlement_time = _parse_aware_time(seller_settlement.get("time"))
        buyer_settlement_time = _parse_aware_time(buyer_settlement.get("time"))
        settlement_times = (seller_settlement_time, buyer_settlement_time)
        if (
            reserve_time is None or buy_reserve_time is None
            or any(stamp is None for stamp in settlement_times)
            or any(
                stamp <= reserve_time or stamp <= buy_reserve_time or stamp > trade_time
                for stamp in settlement_times
            )
            or (trade_time - max(settlement_times)).total_seconds() > 5
        ):
            return False
        return True

    def _is_verified_missed_release_correction(order_id):
        return _verified_missed_release_correction(order_id)

    # Detect duplicates within each source independently. Do not silently
    # de-duplicate equal IDs across the Credits and SLH token domains.
    for ledger_name, source in sources:
        source_ids = [
            _event_id(event)
            for _, event in source
            if _event_id(event) and _is_exchange_audit_event(event)
        ]
        duplicates = sorted(
            event_id
            for event_id, count in Counter(source_ids).items()
            if count > 1
        )
        if duplicates:
            findings.append({
                "code": "DUPLICATE_LEDGER_EVENT_ID",
                "ledger": ledger_name,
                "event_ids": duplicates,
            })

    source_id_maps = {}
    for ledger_name, source in sources:
        by_id = {}
        for _, event in source:
            event_id = _event_id(event)
            if event_id and _is_exchange_audit_event(event):
                by_id.setdefault(event_id, []).append(event)
        source_id_maps[ledger_name] = by_id

    shared_ids = set(source_id_maps["ledger"]) & set(source_id_maps["slh_token_ledger"])
    for event_id in sorted(shared_ids):
        paired = (
            source_id_maps["ledger"][event_id]
            + source_id_maps["slh_token_ledger"][event_id]
        )
        relevant = False
        order_ids = set()
        for event in paired:
            oid = _order_id(event)
            if oid:
                order_ids.add(oid)
            if _is_exchange_audit_event(event):
                relevant = True
        verified_mirrored_correction = (
            len(order_ids) == 1
            and _is_verified_missed_release_correction(next(iter(order_ids)))
            and event_id == f"correction:missed_release:{next(iter(order_ids))}"
        )
        if relevant and not verified_mirrored_correction:
            findings.append({
                "code": "CROSS_LEDGER_EVENT_ID_REQUIRES_REVIEW",
                "event_id": event_id,
                "ledgers": ["ledger", "slh_token_ledger"],
                "order_ids": sorted(order_ids),
                "note": "Shared event IDs are not de-duplicated across accounting domains.",
            })

    # Corrections remain unresolved evidence. Missing event IDs are findings
    # for post-policy rows, unknown-order rows, corrections and undated/malformed
    # timestamps. Known ordinary reserve/release rows predating the policy are
    # exempt from the metadata-only finding, but accounting findings still apply.
    for ledger_name, source in sources:
        for _, event in source:
            reserve, release, correction = _event_groups(event)
            oid = _order_id(event)
            related = _is_exchange_audit_event(event)
            if related and not _event_id(event):
                group = "correction" if correction else "reserve" if reserve else "normal_release"
                # The policy did not require event_id before 2026-09-28.
                # Exempt only ordinary reserve/release metadata for a known order
                # with a valid pre-cutoff timestamp. Corrections, unknown orders,
                # missing timestamps and malformed timestamps still fail closed.
                legacy_metadata_only = (
                    group in {"reserve", "normal_release"}
                    and bool(oid)
                    and oid in known_order_ids
                    and _predates_event_id_requirement(event)
                )
                if not legacy_metadata_only:
                    findings.append({
                        "code": "LEDGER_EVENT_ID_MISSING",
                        "ledger": ledger_name,
                        "order_id": oid or None,
                        "group": group,
                    })
            if correction and related and oid and oid not in known_order_ids:
                findings.append({
                    "code": "ORPHAN_RESERVE_CORRECTION",
                    "ledger": ledger_name,
                    "order_id": oid,
                    "event_id": _event_id(event) or None,
                })

    checked = 0
    for oid, order in sorted(orders.items()):
        side = str(order.get("side", "")).lower()
        status = str(order.get("status", "")).lower()
        if side != "sell" or status not in {"cancelled", "canceled", "closed", "expired"}:
            continue

        per_ledger = {}
        active_ledgers = []
        for ledger_name, source in sources:
            order_events = [
                event for _, event in source
                if _order_id(event) == oid
            ]
            reserve_events = []
            normal_releases = []
            order_corrections = []
            for event in order_events:
                reserve, release, correction = _event_groups(event)
                if reserve:
                    reserve_events.append(event)
                if release:
                    normal_releases.append(event)
                if correction:
                    order_corrections.append(event)
            if reserve_events or normal_releases or order_corrections:
                active_ledgers.append(ledger_name)
            if reserve_events:
                per_ledger[ledger_name] = {
                    "reserve": reserve_events,
                    "normal_release": normal_releases,
                    "correction": order_corrections,
                }
            elif order_corrections:
                # Corrections without a reserve in this same ledger are still
                # reported as unresolved, never used to balance another ledger.
                per_ledger[ledger_name] = {
                    "reserve": [],
                    "normal_release": normal_releases,
                    "correction": order_corrections,
                }

        if not any(groups["reserve"] for groups in per_ledger.values()):
            continue
        checked += 1
        verified_mirrored_correction = _is_verified_missed_release_correction(oid)
        verified_legacy_trade_settlement = _verified_legacy_trade_settlement(oid)
        if len(active_ledgers) > 1 and not verified_mirrored_correction:
            findings.append({
                "code": "MIXED_LEDGER_DOMAINS_REQUIRES_REVIEW",
                "order_id": oid,
                "ledgers": active_ledgers,
                "note": "Credits and SLH token entries are checked independently and never netted together.",
            })

        for ledger_name, groups in per_ledger.items():
            reserve_events = groups["reserve"]
            normal_releases = groups["normal_release"]
            order_corrections = groups["correction"]
            amount_groups = {
                "reserve": reserve_events,
                "normal_release": normal_releases,
                "correction": order_corrections,
            }
            parsed_amounts = {
                name: [(event, _amount(event.get("amount"))) for event in group]
                for name, group in amount_groups.items()
            }
            invalid_amounts = [
                {
                    "event_id": _event_id(event),
                    "group": group_name,
                }
                for group_name, rows in parsed_amounts.items()
                for event, amount in rows
                if amount is None
            ]
            if invalid_amounts:
                findings.append({
                    "code": "INVALID_RESERVE_LEDGER_AMOUNT",
                    "ledger": ledger_name,
                    "order_id": oid,
                    "events": invalid_amounts,
                    "note": "Missing or non-finite amounts prevent reliable reserve reconciliation.",
                })

            reserve_total = sum(
                (
                    _ledger_delta(event, amount, "reserve", ledger_name)
                    for event, amount in parsed_amounts["reserve"]
                    if amount is not None
                ),
                Decimal(0),
            )
            release_total = sum(
                (
                    _ledger_delta(event, amount, "normal_release", ledger_name)
                    for event, amount in parsed_amounts["normal_release"]
                    if amount is not None
                ),
                Decimal(0),
            )
            correction_total = sum(
                (amount for _, amount in parsed_amounts["correction"] if amount is not None),
                Decimal(0),
            )

            if (
                reserve_events and not normal_releases
                and not verified_mirrored_correction
                and not verified_legacy_trade_settlement
            ):
                findings.append({
                    "code": "CANCELLED_SELL_ORDER_MISSING_NORMAL_RELEASE",
                    "ledger": ledger_name,
                    "order_id": oid,
                    "uid_suffix": str(order.get("uid_suffix") or str(order.get("uid") or order.get("user_id") or "")[-4:]),
                    "reserve_delta": str(reserve_total),
                    "correction_delta": str(correction_total),
                    "note": "Manual correction is evidence to review, not proof of normal reserve release.",
                })
            if order_corrections and not verified_mirrored_correction:
                findings.append({
                    "code": "MANUAL_RESERVE_CORRECTION_REQUIRES_REVIEW",
                    "ledger": ledger_name,
                    "order_id": oid,
                    "event_ids": sorted(_event_id(event) for event in order_corrections),
                    "correction_delta": str(correction_total),
                })
            net_delta = reserve_total + release_total
            if (
                reserve_events and net_delta != 0 and not order_corrections
                and not verified_legacy_trade_settlement
            ):
                findings.append({
                    "code": "RESERVE_DELTA_NOT_ZERO",
                    "ledger": ledger_name,
                    "order_id": oid,
                    "reserve_delta": str(reserve_total),
                    "normal_release_delta": str(release_total),
                    "net_delta": str(net_delta),
                })

    if checked == 0:
        findings.append({
            "code": "NO_CANCELLED_SELL_ORDERS_WITH_RESERVE_FOUND",
            "note": "No eligible reserve records were matched; the audit cannot claim PASS.",
        })

    # Add sanitized current-state context, without suppressing findings or changing
    # the complete historical audit result.
    for item in findings:
        if item.get("order_id"):
            item.update(_current_order_context(item["order_id"]))

    terminal_statuses = {"cancelled", "canceled", "closed", "expired"}

    def _current_reserve_state_is_proven(order_id):
        order = orders.get(str(order_id))
        if not isinstance(order, dict):
            return False
        context = _current_order_context(order_id)
        return (
            str(order.get("side") or "").lower() == "sell"
            and str(order.get("status") or "").lower() in terminal_statuses
            and context.get("order_remaining_is_zero") is True
            and context.get("order_reserved_slh_is_zero") is True
            # Other open sell orders may legitimately reserve SLH in this wallet.
            # Prove that this terminal order released its own reserve and that
            # the wallet total exactly matches the independent open-order book.
            # Requiring the whole wallet reserve to be zero confuses unrelated
            # live reservations with a terminal-order reconciliation failure.
            and context.get("wallet_reserve_matches_open_orders") is True
        )

    def _archived_test_seed_finding_is_nonblocking(item):
        raw_ids = []
        if item.get("order_id"):
            raw_ids = [str(item.get("order_id"))]
        elif isinstance(item.get("order_ids"), list):
            raw_ids = [str(oid) for oid in item["order_ids"] if oid]
        if not raw_ids:
            return False
        for oid in raw_ids:
            order = orders.get(oid)
            context = _current_order_context(oid)
            if (
                not isinstance(order, dict)
                or order_source_by_id.get(oid) != "archive"
                or context.get("order_is_archived_test_seed") is not True
                or not _current_reserve_state_is_proven(oid)
            ):
                return False
        return True

    def _legacy_balanced_cancelled_order_is_nonblocking(item):
        if item.get("code") != "LEDGER_EVENT_ID_MISSING":
            return False
        if item.get("group") not in {"reserve", "normal_release"}:
            return False
        oid = str(item.get("order_id") or "")
        ledger_name = str(item.get("ledger") or "")
        order = orders.get(oid)
        if (
            not oid
            or ledger_name not in {"ledger", "slh_token_ledger"}
            or not isinstance(order, dict)
            or order_source_by_id.get(oid) != "active"
            or str(order.get("side") or "").lower() != "sell"
            or str(order.get("status") or "").lower() not in terminal_statuses
            or not _current_reserve_state_is_proven(oid)
        ):
            return False
        context = _current_order_context(oid)
        # Do not infer "legacy" from missing IDs alone. It must be an ordinary,
        # non-seed order with a proved empty current reserve and matching order book.
        if context.get("order_is_test_seed") is not False:
            return False
        ledger_source = dict(sources).get(ledger_name)
        if not isinstance(ledger_source, list):
            return False
        order_events = [
            event for _, event in ledger_source
            if _order_id(event) == oid and _is_exchange_audit_event(event)
        ]
        reserve_events = []
        release_events = []
        correction_events = []
        for event in order_events:
            reserve, release, correction = _event_groups(event)
            if reserve:
                reserve_events.append(event)
            if release:
                release_events.append(event)
            if correction:
                correction_events.append(event)
        # Missing-ID classification is only acceptable when the paired rows
        # are unique, tied to this terminal order, and contain no correction.
        if (
            len(reserve_events) != 1
            or len(release_events) != 1
            or correction_events
            or not any(not _event_id(event) for event in reserve_events + release_events)
        ):
            return False
        parsed_reserve = [(_amount(event.get("amount")), event) for event in reserve_events]
        parsed_release = [(_amount(event.get("amount")), event) for event in release_events]
        if any(amount is None for amount, _ in parsed_reserve + parsed_release):
            return False
        reserve_total = sum(
            (_ledger_delta(event, amount, "reserve", ledger_name) for amount, event in parsed_reserve),
            Decimal(0),
        )
        release_total = sum(
            (_ledger_delta(event, amount, "normal_release", ledger_name) for amount, event in parsed_release),
            Decimal(0),
        )
        return reserve_total + release_total == 0

    blocking_findings = []
    historical_findings = []
    for item in findings:
        if _archived_test_seed_finding_is_nonblocking(item):
            item["operational_classification"] = "HISTORICAL_ARCHIVED_TEST_SEED"
            historical_findings.append(item)
        elif _legacy_balanced_cancelled_order_is_nonblocking(item):
            item["operational_classification"] = "LEGACY_BALANCED_CANCELLED_ORDER"
            historical_findings.append(item)
        else:
            item["operational_classification"] = "BLOCKING"
            blocking_findings.append(item)

    # Fail closed: an allowlist of blocker codes can silently downgrade a
    # newly introduced or misspelled finding. Every finding blocks release
    # unless a narrowly-scoped, explicitly verified historical exception above
    # has already classified it as non-blocking.
    release_blocking_findings = [
        item for item in findings
        if item.get("operational_classification") == "BLOCKING"
        or str(item.get("code") or "") in RELEASE_GATE_BLOCKER_CODES
    ]
    if checked == 0:
        # No matched reserve history is not evidence of a clean release.
        release_blocking_findings.append({
            "code": "RESERVE_HISTORY_NOT_PROVEN",
            "note": "The audit could not match any cancelled sell reserve history.",
        })
    release_readiness_status = "BLOCKED" if release_blocking_findings else "PASS"

    status = "FAIL" if any(
        item.get("code") != "NO_CANCELLED_SELL_ORDERS_WITH_RESERVE_FOUND"
        for item in findings
    ) else ("UNKNOWN" if checked == 0 else "PASS")
    # Operational reserve consistency and financial-release permission are
    # separate decisions. Archived seed state can be operationally retired yet
    # still require accounting review before public trading is enabled.
    operational_status = (
        "UNKNOWN" if checked == 0
        else "BLOCKED" if blocking_findings
        else "PASS"
    )

    return {
        "status": status,
        "operational_status": operational_status,
        "release_readiness_status": release_readiness_status,
        "release_blocking_finding_count": len(release_blocking_findings),
        "release_blocking_findings": release_blocking_findings,
        "read_only": True,
        "checked_cancelled_sell_orders": checked,
        "finding_count": len(findings),
        "findings": findings,
        "blocking_finding_count": len(blocking_findings),
        "blocking_findings": blocking_findings,
        "historical_finding_count": len(historical_findings),
        "historical_findings": historical_findings,
    }


def run_once():
    db = state_manager.load_db()
    return audit_db(db)


def _safe_log_finding(item, index):
    """Keep operational logs useful without emitting arbitrary DB fields."""
    if not isinstance(item, dict):
        return {"index": index, "code": "MALFORMED_FINDING"}

    allowed = (
        "code",
        "ledger",
        "ledgers",
        "order_id",
        "order_ids",
        "trade_id",
        "order_status",
        "order_remaining_is_zero",
        "order_reserved_slh_is_zero",
        "wallet_reserved_slh_is_zero",
        "wallet_reserve_matches_open_orders",
        "order_is_archived",
        "order_is_test_seed",
        "order_is_archived_test_seed",
        "operational_classification",
        "group",
        "uid_suffix",
        "reserve_delta",
        "normal_release_delta",
        "release_delta",
        "net_delta",
        "correction_delta",
        "event_id",
        "event_ids",
    )
    safe = {"index": index}
    for key in allowed:
        if key not in item or item[key] is None:
            continue
        value = item[key]
        if key == "uid_suffix":
            suffix = "".join(char for char in str(value) if char.isdigit())[-4:]
            if suffix:
                safe[key] = suffix
            continue
        if isinstance(value, list):
            limit = 4 if key in {"ledgers", "order_ids"} else 3
            safe[key] = [
                str(entry).replace("\n", " ").replace("\\r", " ")[:80]
                for entry in value[:limit]
                if entry is not None
            ]
        elif isinstance(value, (str, int, float, bool)):
            rendered = str(value).replace("\n", " ").replace("\\r", " ")
            safe[key] = rendered[:100] if isinstance(value, str) else value
        else:
            safe[key] = str(value).replace("\n", " ").replace("\\r", " ")[:100]
    return safe


def _reserve_audit_log_chunks(findings, chunk_size=5):
    """Format every finding as bounded, sanitized one-line JSON chunks."""
    if not isinstance(findings, list):
        return []
    safe_findings = [
        _safe_log_finding(item, index)
        for index, item in enumerate(findings, start=1)
    ]
    return [
        json.dumps(safe_findings[offset:offset + chunk_size], ensure_ascii=False, separators=(",", ":"))
        for offset in range(0, len(safe_findings), chunk_size)
    ]


def run_periodic(log, interval_seconds=None):
    """Log read-only findings periodically; callers should run this in a daemon thread."""
    configured = interval_seconds or int(os.getenv("SLH_EXCHANGE_RECONCILIATION_INTERVAL_SECONDS", "900"))
    interval = max(60, configured)
    while True:
        try:
            report = run_once()
            findings = report.get("findings")
            findings = findings if isinstance(findings, list) else []
            log(
                "[SLH_EXCHANGE_RECONCILIATION] "
                f"status={report['status']} "
                f"operational_status={report.get('operational_status', 'UNKNOWN')} "
                f"release_readiness_status={report.get('release_readiness_status', 'UNKNOWN')} "
                f"release_blocking_finding_count={report.get('release_blocking_finding_count', 0)} "
                f"blocking_finding_count={report.get('blocking_finding_count', len(findings))} "
                f"historical_finding_count={report.get('historical_finding_count', 0)} "
                f"checked_cancelled_sell_orders={report['checked_cancelled_sell_orders']} "
                f"finding_count={report['finding_count']} "
                f"logged_finding_count={len(findings)}"
            )
            chunks = _reserve_audit_log_chunks(findings)
            for part_number, chunk in enumerate(chunks, start=1):
                log(
                    "[SLH_EXCHANGE_RECONCILIATION_DETAILS] "
                    f"part={part_number}/{len(chunks)} findings={chunk}"
                )
        except Exception as exc:
            log(f"[SLH_EXCHANGE_RECONCILIATION] status=UNKNOWN error={type(exc).__name__}: {str(exc)[:200]}")
        time.sleep(interval)
