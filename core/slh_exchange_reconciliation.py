"""Read-only SLH exchange reserve reconciliation.

This module reports discrepancies only. It never mutates balances, orders,
ledgers, freezes, or exchange gates.
"""
from __future__ import annotations

from collections import Counter
import json
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
    for key, order in _records(db.get("exchange_orders", {})) + _records(db.get("exchange_order_archive", {})):
        oid = str(order.get("order_id") or order.get("id") or key)
        orders[oid] = order

    sources = (
        ("ledger", _records(db.get("ledger", []))),
        ("slh_token_ledger", _records(db.get("slh_token_ledger", []))),
    )
    known_order_ids = set(orders)

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

        if correction:
            # The general Credits ledger also contains non-exchange corrections.
            # Only include corrections evidenced as exchange/reserve-specific,
            # or explicitly attached to a known exchange order.
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
            or reason.startswith("exchange:")
            or kind.startswith("exchange_")
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

    # Corrections remain unresolved evidence. Missing IDs are also findings for
    # exchange reserve/release/correction rows; they are never silently ignored.
    for ledger_name, source in sources:
        for _, event in source:
            reserve, release, correction = _event_groups(event)
            oid = _order_id(event)
            related = _is_exchange_audit_event(event)
            if related and not _event_id(event):
                findings.append({
                    "code": "LEDGER_EVENT_ID_MISSING",
                    "ledger": ledger_name,
                    "order_id": oid or None,
                    "group": "correction" if correction else "reserve" if reserve else "normal_release",
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
                str(entry).replace("\\n", " ").replace("\\r", " ")[:80]
                for entry in value[:limit]
                if entry is not None
            ]
        elif isinstance(value, (str, int, float, bool)):
            rendered = str(value).replace("\\n", " ").replace("\\r", " ")
            safe[key] = rendered[:100] if isinstance(value, str) else value
        else:
            safe[key] = str(value).replace("\\n", " ").replace("\\r", " ")[:100]
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
