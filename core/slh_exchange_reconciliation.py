"""Read-only SLH exchange reserve reconciliation.

This module reports discrepancies only. It never mutates balances, orders,
ledgers, freezes, or exchange gates.
"""
from __future__ import annotations

from collections import Counter
from decimal import Decimal, InvalidOperation
import os
import time

import state_manager


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


def audit_db(db):
    """Return a stable, read-only audit report for exchange sell reserves."""
    findings = []
    orders = {}
    for key, order in _records(db.get("exchange_orders", {})) + _records(db.get("exchange_order_archive", {})):
        oid = str(order.get("order_id") or order.get("id") or key)
        orders[oid] = order

    legacy_ledger = _records(db.get("ledger", []))
    token_ledger = _records(db.get("slh_token_ledger", []))

    # The same logical event can be mirrored in both ledgers. Detect duplicates
    # within each source, then de-duplicate mirrored records for amount totals.
    duplicate_event_ids = set()
    for source in (legacy_ledger, token_ledger):
        source_ids = []
        for _, event in source:
            meta = event.get("meta") if isinstance(event.get("meta"), dict) else {}
            event_id = event.get("event_id") or meta.get("event_id")
            if event_id:
                source_ids.append(str(event_id))
        duplicate_event_ids.update(
            event_id for event_id, count in Counter(source_ids).items() if count > 1
        )
    if duplicate_event_ids:
        findings.append({"code": "DUPLICATE_LEDGER_EVENT_ID", "event_ids": sorted(duplicate_event_ids)})

    events = []
    seen_event_ids = set()
    for _, event in legacy_ledger + token_ledger:
        meta = event.get("meta") if isinstance(event.get("meta"), dict) else {}
        event_id = event.get("event_id") or meta.get("event_id")
        if event_id and str(event_id) in seen_event_ids:
            continue
        if event_id:
            seen_event_ids.add(str(event_id))
        events.append(event)

    known_order_ids = set(orders)
    corrections = []
    for event in events:
        reason = str(event.get("reason", "")).lower()
        kind = str(event.get("kind", "")).lower()
        if "correction" in reason or "correction" in kind:
            meta = event.get("meta") if isinstance(event.get("meta"), dict) else {}
            oid = str(event.get("order_id") or meta.get("order_id") or "")
            if oid:
                corrections.append((oid, event))
                if oid not in known_order_ids:
                    findings.append({"code": "ORPHAN_RESERVE_CORRECTION", "order_id": oid,
                                     "event_id": event.get("event_id")})

    checked = 0
    for oid, order in sorted(orders.items()):
        side = str(order.get("side", "")).lower()
        status = str(order.get("status", "")).lower()
        if side != "sell" or status not in {"cancelled", "canceled", "closed", "expired"}:
            continue
        order_events = []
        for event in events:
            meta = event.get("meta") if isinstance(event.get("meta"), dict) else {}
            event_oid = str(event.get("order_id") or meta.get("order_id") or "")
            if event_oid == oid:
                order_events.append(event)
        reserve_events = [
            e for e in order_events
            if "sell_reserve" in str(e.get("reason", "")).lower()
            or "sell_reserve" in str(e.get("kind", "")).lower()
        ]
        if not reserve_events:
            continue
        checked += 1
        normal_releases = [
            e for e in order_events
            if ("release" in str(e.get("reason", "")).lower()
                or "release" in str(e.get("kind", "")).lower())
            and "correction" not in str(e.get("reason", "")).lower()
            and "correction" not in str(e.get("kind", "")).lower()
        ]
        order_corrections = [
            e for e in order_events
            if "correction" in str(e.get("reason", "")).lower()
            or "correction" in str(e.get("kind", "")).lower()
        ]
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
            {"event_id": str(event.get("event_id") or (
                event.get("meta", {}).get("event_id")
                if isinstance(event.get("meta"), dict) else ""
            ) or ""), "group": name}
            for name, rows in parsed_amounts.items()
            for event, amount in rows
            if amount is None
        ]
        if invalid_amounts:
            findings.append({
                "code": "INVALID_RESERVE_LEDGER_AMOUNT",
                "order_id": oid,
                "events": invalid_amounts,
                "note": "Missing or non-finite amounts prevent reliable reserve reconciliation.",
            })
        reserve_total = sum((amount for _, amount in parsed_amounts["reserve"] if amount is not None), Decimal(0))
        release_total = sum((amount for _, amount in parsed_amounts["normal_release"] if amount is not None), Decimal(0))
        correction_total = sum((amount for _, amount in parsed_amounts["correction"] if amount is not None), Decimal(0))
        if not normal_releases:
            findings.append({
                "code": "CANCELLED_SELL_ORDER_MISSING_NORMAL_RELEASE",
                "order_id": oid,
                "uid_suffix": str(order.get("uid_suffix") or str(order.get("uid") or order.get("user_id") or "")[-4:]),
                "reserve_delta": str(reserve_total),
                "correction_delta": str(correction_total),
                "note": "Manual correction is evidence to review, not proof of normal reserve release.",
            })
        if order_corrections:
            findings.append({
                "code": "MANUAL_RESERVE_CORRECTION_REQUIRES_REVIEW",
                "order_id": oid,
                "event_ids": sorted(
                    str(e.get("event_id") or (
                        e.get("meta", {}).get("event_id")
                        if isinstance(e.get("meta"), dict) else ""
                    ) or "")
                    for e in order_corrections
                ),
                "correction_delta": str(correction_total),
            })
        if reserve_total + release_total != 0 and not order_corrections:
            findings.append({
                "code": "RESERVE_DELTA_NOT_ZERO",
                "order_id": oid,
                "reserve_delta": str(reserve_total),
                "normal_release_delta": str(release_total),
                "net_delta": str(reserve_total + release_total),
            })

    if checked == 0:
        findings.append({
            "code": "NO_CANCELLED_SELL_ORDERS_WITH_RESERVE_FOUND",
            "note": "No eligible reserve records were matched; the audit cannot claim PASS.",
        })

    status = "FAIL" if any(
        item.get("code") != "NO_CANCELLED_SELL_ORDERS_WITH_RESERVE_FOUND"
        for item in findings
    ) else ("UNKNOWN" if checked == 0 else "PASS")

    return {
        "status": status,
        "read_only": True,
        "checked_cancelled_sell_orders": checked,
        "finding_count": len(findings),
        "findings": findings,
    }


def run_once():
    db = state_manager.load_db()
    return audit_db(db)


def run_periodic(log, interval_seconds=None):
    """Log read-only findings periodically; callers should run this in a daemon thread."""
    configured = interval_seconds or int(os.getenv("SLH_EXCHANGE_RECONCILIATION_INTERVAL_SECONDS", "900"))
    interval = max(60, configured)
    while True:
        try:
            report = run_once()
            log(
                "[SLH_EXCHANGE_RECONCILIATION] "
                f"status={report['status']} "
                f"checked_cancelled_sell_orders={report['checked_cancelled_sell_orders']} "
                f"finding_count={report['finding_count']} "
                f"findings={report['findings'][:20]}"
            )
        except Exception as exc:
            log(f"[SLH_EXCHANGE_RECONCILIATION] status=UNKNOWN error={type(exc).__name__}: {str(exc)[:200]}")
        time.sleep(interval)
