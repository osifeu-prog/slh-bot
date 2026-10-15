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
        if relevant:
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
        if len(active_ledgers) > 1:
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

            if reserve_events and not normal_releases:
                findings.append({
                    "code": "CANCELLED_SELL_ORDER_MISSING_NORMAL_RELEASE",
                    "ledger": ledger_name,
                    "order_id": oid,
                    "uid_suffix": str(order.get("uid_suffix") or str(order.get("uid") or order.get("user_id") or "")[-4:]),
                    "reserve_delta": str(reserve_total),
                    "correction_delta": str(correction_total),
                    "note": "Manual correction is evidence to review, not proof of normal reserve release.",
                })
            if order_corrections:
                findings.append({
                    "code": "MANUAL_RESERVE_CORRECTION_REQUIRES_REVIEW",
                    "ledger": ledger_name,
                    "order_id": oid,
                    "event_ids": sorted(_event_id(event) for event in order_corrections),
                    "correction_delta": str(correction_total),
                })
            net_delta = reserve_total + release_total
            if reserve_events and net_delta != 0 and not order_corrections:
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

    release_blocking_findings = [
        item for item in findings
        if str(item.get("code") or "") in RELEASE_GATE_BLOCKER_CODES
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
