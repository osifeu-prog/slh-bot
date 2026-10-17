"""Read-only diagnostics for a single user's canonical Credits ledger sequence.

This module never repairs or rewrites balances. It may reconcile a specifically
allow-listed historical transition only when its version-controlled source
snapshot and exact source/destination deltas match. Domain hints remain heuristic.
"""
from __future__ import annotations

import math
from typing import Any

EPSILON = 1e-8
MAX_FINDINGS = 25

# Source-backed, one-time consolidation found in the version-controlled DB
# transition at d013b914bbca1b6c2f50e768d461213ae1cbfbef. That commit records
# the source wallet (10449 Credits + 50 staked), removes that source account,
# and moves the destination Credits wallet from 1316 to 11815. The ledger row
# is at index 2 in the persisted history. This allow-list is deliberately exact:
# it does not authorize generic alpha_consolidate rows.
_VERIFIED_ALPHA_CONSOLIDATION = {
    "time": "2026-08-22T16:12:41.978584+00:00",
    "from": "8791275334",
    "to": "8789977826",
    "credits": 10449.0,
    "staked_moved": 50.0,
    "reason": "OWNER_ONLY_CREDITS_POLICY",
    "previous_index": 1,
    "event_index": 2,
    "next_index": 3,
    "previous_after": 1316.0,
    "next_before": 11815.0,
    "source_commit": "d013b914bbca1b6c2f50e768d461213ae1cbfbef",
    "source_commit_url": "https://github.com/osifeu-prog/slh-bot/commit/d013b914bbca1b6c2f50e768d461213ae1cbfbef",
}


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def _reason_domain_hint(reason: Any) -> str:
    """Return a clue only; never treat reason names as proof of accounting domain."""
    text = str(reason or "").strip().lower()
    slh_exact = {
        "exchange:sell_reserve",
        "exchange:cancel_release_slh",
        "p2p:slh_sent",
        "p2p:slh_received",
    }
    credits_exact = {
        "exchange:buy_reserve",
        "exchange:cancel_release_credits",
        "exchange:settlement_credits",
        "p2p:credits_sent",
        "p2p:credits_received",
        "bnb:deposit",
        "ton:deposit",
        "store:purchase",
    }
    if text in slh_exact or text.startswith("p2p:slh:") or text.startswith("slh:"):
        return "SLH_HINT"
    if text in credits_exact or text.startswith("staking:"):
        return "CREDITS_HINT"
    if "credits" in text:
        return "CREDITS_HINT"
    return "UNKNOWN_HINT"


def _row_domain_hint(row: dict) -> str:
    """Use explicit domain metadata; keep reason-only SLH labels ambiguous."""
    meta = row.get("meta")
    meta = meta if isinstance(meta, dict) else {}
    explicit = str(meta.get("ledger_domain") or meta.get("asset") or "").strip().lower()
    if explicit:
        if "slh" in explicit or "token" in explicit:
            return "SLH_HINT"
        if "credit" in explicit:
            return "CREDITS_HINT"
    inferred = _reason_domain_hint(row.get("reason"))
    # A heuristic SLH label must not remove a row from the Credits continuity
    # check. Without explicit domain metadata, retain it as ambiguous so any
    # continuity gap remains visible and blocks release readiness.
    if inferred == "SLH_HINT":
        return "AMBIGUOUS_DOMAIN_HINT"
    return inferred


def _row_summary(index: int, row: dict) -> dict:
    meta = row.get("meta")
    meta = meta if isinstance(meta, dict) else {}
    tx_hash = str(meta.get("tx_hash") or "").strip()
    return {
        "index": index,
        "time": str(row.get("time") or "")[:32],
        "reason": str(row.get("reason") or "UNKNOWN")[:80],
        "domain_hint": _row_domain_hint(row),
        "before": _number(row.get("before")),
        "amount": _number(row.get("amount")),
        "after": _number(row.get("after")),
        "tx_suffix": tx_hash[-8:] if tx_hash else None,
        "order_id": str(meta.get("order_id") or "")[:40] or None,
        "event_id": str(row.get("event_id") or meta.get("event_id") or "")[:64] or None,
        "transfer_id": str(meta.get("transfer_id") or "")[:80] or None,
        "purchase_id": str(meta.get("purchase_id") or "")[:120] or None,
        "idempotency_key": str(meta.get("idempotency_key") or "")[:120] or None,
        "item_id": str(meta.get("item_id") or "")[:80] or None,
    }


def _source_evidence_for_gap(db: dict, previous: dict, next_row: dict, uid: str = "") -> dict:
    """Return linked source-record context for a gap without resolving it.

    Source records may explain a transaction's purpose, but they are never
    treated as proof that a balance discontinuity is reconciled.
    """
    evidence: dict[str, Any] = {}
    ledger = db.get("ledger") if isinstance(db.get("ledger"), list) else []

    transfer_id = str(previous.get("transfer_id") or next_row.get("transfer_id") or "").strip()
    if transfer_id:
        transfer_rows = []
        for index, row in enumerate(ledger):
            if not isinstance(row, dict):
                continue
            meta = row.get("meta")
            meta = meta if isinstance(meta, dict) else {}
            linked_id = str(meta.get("transfer_id") or row.get("transfer_id") or "").strip()
            if linked_id != transfer_id:
                continue
            transfer_rows.append({
                "index": index,
                "uid": str(row.get("uid") or ""),
                "reason": str(row.get("reason") or "UNKNOWN")[:80],
                "before": _number(row.get("before")),
                "amount": _number(row.get("amount")),
                "after": _number(row.get("after")),
            })
        processed = db.get("processed_transfers")
        processed_keys = [
            str(key) for key, value in processed.items()
            if str(value) == transfer_id
        ][:5] if isinstance(processed, dict) else []
        evidence["transfer"] = {
            "transfer_id": transfer_id,
            "ledger_rows": transfer_rows[:8],
            "processed_keys": processed_keys,
            "record_found": bool(transfer_rows or processed_keys),
        }

    purchase_id = str(next_row.get("purchase_id") or previous.get("purchase_id") or "").strip()
    if purchase_id:
        purchases = db.get("purchases")
        record = purchases.get(purchase_id) if isinstance(purchases, dict) else None
        if not isinstance(record, dict) and isinstance(purchases, dict):
            record = next(
                (item for item in purchases.values()
                 if isinstance(item, dict) and str(item.get("purchase_id") or "") == purchase_id),
                None,
            )
        if isinstance(record, dict):
            fulfillment = record.get("fulfillment")
            fulfillment = fulfillment if isinstance(fulfillment, dict) else {}
            evidence["purchase"] = {
                "purchase_id": purchase_id,
                "record_found": True,
                "status": str(record.get("status") or "UNKNOWN")[:40],
                "uid": str(record.get("uid") or ""),
                "seller_uid": str(record.get("seller_uid") or ""),
                "item_id": str(record.get("item_id") or "")[:80],
                "price": _number(record.get("price")),
                "seller_payout": _number(record.get("seller_payout")),
                "commission": _number(record.get("commission")),
                "created_at": str(record.get("created_at") or "")[:40],
                "fulfillment_method": str(fulfillment.get("method") or "")[:40],
            }
        else:
            evidence["purchase"] = {
                "purchase_id": purchase_id,
                "record_found": False,
            }

    # alpha_consolidate is a global event rather than a per-user Credits row.
    # One exact historical instance has independent version-controlled source
    # evidence; all other rows remain context-only and cannot clear a gap.
    alpha_consolidations = []
    try:
        previous_index = int(previous.get("index", -1))
        next_index = int(next_row.get("index", -1))
    except (TypeError, ValueError, OverflowError):
        previous_index, next_index = -1, -1
    if uid and 0 <= previous_index < next_index < len(ledger):
        previous_after = _number(previous.get("after"))
        next_before = _number(next_row.get("before"))
        observed_delta = (
            next_before - previous_after
            if previous_after is not None and next_before is not None
            else None
        )
        for index in range(previous_index + 1, next_index):
            row = ledger[index]
            if not isinstance(row, dict) or row.get("type") != "alpha_consolidate":
                continue
            if str(row.get("to") or "").strip() != uid:
                continue
            credits_component = _number(row.get("credits"))
            staked_component = _number(row.get("staked_moved"))
            source_uid = str(row.get("from") or "").strip()
            # If the source account still exists, it must no longer retain the
            # amounts migrated by this event. Missing/unreadable values fail closed.
            users_db = db.get("users")
            source_user = users_db.get(source_uid) if isinstance(users_db, dict) else None
            source_wallet = source_user.get("wallet") if isinstance(source_user, dict) else None
            if isinstance(source_user, dict):
                source_credits = _number(source_wallet.get("credits")) if isinstance(source_wallet, dict) else None
                source_staked = _number(source_wallet.get("staked")) if isinstance(source_wallet, dict) else None
                source_account_cleared = (
                    source_credits is not None and source_staked is not None
                    and abs(source_credits) <= EPSILON and abs(source_staked) <= EPSILON
                )
            else:
                # The verified historical commit itself deletes the source account.
                source_account_cleared = True
            verified = _VERIFIED_ALPHA_CONSOLIDATION
            exact_source_event = (
                index == verified["event_index"]
                and previous_index == verified["previous_index"]
                and next_index == verified["next_index"]
                and uid == verified["to"]
                and source_uid == verified["from"]
                and str(row.get("time") or "") == verified["time"]
                and str(row.get("reason") or "") == verified["reason"]
                and credits_component is not None
                and abs(credits_component - verified["credits"]) <= EPSILON
                and staked_component is not None
                and abs(staked_component - verified["staked_moved"]) <= EPSILON
                and previous_after is not None
                and abs(previous_after - verified["previous_after"]) <= EPSILON
                and next_before is not None
                and abs(next_before - verified["next_before"]) <= EPSILON
                and observed_delta is not None
                and abs(observed_delta - (verified["credits"] + verified["staked_moved"])) <= EPSILON
                and source_account_cleared
            )
            alpha_consolidations.append({
                "index": index,
                "time": str(row.get("time") or "")[:40],
                "type": "alpha_consolidate",
                "from": source_uid[:80],
                "to": str(row.get("to") or "")[:80],
                "reason": str(row.get("reason") or "")[:80],
                "credits_component": credits_component,
                "staked_moved_component": staked_component,
                "observed_balance_delta": observed_delta,
                "credits_component_matches_delta": (
                    credits_component is not None
                    and observed_delta is not None
                    and abs(credits_component - observed_delta) <= EPSILON
                ),
                "credits_plus_staked_matches_delta": (
                    credits_component is not None
                    and staked_component is not None
                    and observed_delta is not None
                    and abs((credits_component + staked_component) - observed_delta) <= EPSILON
                ),
                "record_found": True,
                "resolves_gap": bool(exact_source_event),
                "resolution_basis": (
                    "VERSION_CONTROLLED_SOURCE_AND_DESTINATION_STATE_MATCH"
                    if exact_source_event else "CONTEXT_ONLY_REQUIRES_RECONCILIATION"
                ),
                "source_commit": verified["source_commit"] if exact_source_event else None,
                "source_commit_url": verified["source_commit_url"] if exact_source_event else None,
                "historical_source_wallet": (
                    {"credits": 10449.0, "staked": 50.0}
                    if exact_source_event else None
                ),
                "historical_destination_credits": (
                    {"before": 1316.0, "after": 11815.0}
                    if exact_source_event else None
                ),
                "note": (
                    "Exact historical event reconciled against the version-controlled source/destination snapshot; "
                    "read-only classification only."
                    if exact_source_event else
                    "Context only; unverified alpha consolidation rows do not resolve a Credits gap."
                ),
            })
    if alpha_consolidations:
        evidence["alpha_consolidations"] = alpha_consolidations[:5]

    linked = any(
        isinstance(value, dict) and value.get("record_found") is True
        for value in evidence.values()
    )
    verified_alpha = any(
        item.get("resolves_gap") is True for item in alpha_consolidations
    )
    evidence["source_match_status"] = (
        "VERIFIED_HISTORICAL_ALPHA_CONSOLIDATION"
        if verified_alpha
        else (
            "ALPHA_CONSOLIDATION_CONTEXT_REQUIRES_RECONCILIATION"
            if alpha_consolidations
            else ("CONTEXT_ONLY_REQUIRES_RECONCILIATION" if linked else "NO_DIRECT_SOURCE_MATCH")
        )
    )
    evidence["resolves_gap"] = bool(verified_alpha)
    return evidence

def audit_account_ledger(db: Any, uid: Any, *, max_findings: int = MAX_FINDINGS) -> dict:
    """Check per-user row arithmetic, sequence continuity, and wallet/tail equality."""
    uid = str(uid or "").strip()
    try:
        limit = max(1, min(int(max_findings), MAX_FINDINGS))
    except (TypeError, ValueError, OverflowError):
        limit = MAX_FINDINGS

    if not uid:
        return {
            "scope": "read_only", "status": "BLOCKED", "uid": None,
            "rows_checked": 0, "continuity_break_count": 0,
            "arithmetic_error_count": 0, "malformed_global_rows": 0,
            "current_balance_matches_tail": False, "findings": [],
            "blockers": ["UID_MISSING"],
        }
    if not isinstance(db, dict) or not isinstance(db.get("ledger"), list):
        return {
            "scope": "read_only", "status": "BLOCKED", "uid": uid,
            "rows_checked": 0, "continuity_break_count": 0,
            "arithmetic_error_count": 0, "malformed_global_rows": 0,
            "current_balance_matches_tail": False, "findings": [],
            "blockers": ["LEDGER_UNREADABLE"],
        }

    ledger = db["ledger"]
    users = db.get("users")
    user = users.get(uid) if isinstance(users, dict) else None
    wallet = user.get("wallet") if isinstance(user, dict) else None
    current_balance = _number(wallet.get("credits")) if isinstance(wallet, dict) else None

    rows_checked = 0
    sequence_rows_checked = 0
    non_credits_rows_skipped = 0
    gap_count = 0
    resolved_gap_count = 0
    unresolved_gap_count = 0
    arithmetic_count = 0
    malformed_global_rows = 0
    findings = []
    previous = None
    last_summary = None

    for index, row in enumerate(ledger):
        if not isinstance(row, dict):
            malformed_global_rows += 1
            previous = None
            if len(findings) < limit:
                findings.append({
                    "type": "MALFORMED_GLOBAL_LEDGER_ROW",
                    "index": index,
                    "reason": "Non-dict row; owner cannot be established safely",
                })
            continue
        if str(row.get("uid") or "").strip() != uid:
            continue

        rows_checked += 1
        summary = _row_summary(index, row)
        # Only explicit asset/domain metadata is authoritative enough to skip
        # an SLH-token row here. Reason-only SLH guesses are labeled ambiguous
        # by _row_domain_hint() and remain in the sequence, failing closed if
        # they create a continuity gap.
        if summary["domain_hint"] == "SLH_HINT":
            non_credits_rows_skipped += 1
            continue
        sequence_rows_checked += 1
        before, amount, after = summary["before"], summary["amount"], summary["after"]
        if before is None or amount is None or after is None or abs((before + amount) - after) > EPSILON:
            arithmetic_count += 1
            if len(findings) < limit:
                findings.append({
                    "type": "ROW_ARITHMETIC_INVALID",
                    "row": summary,
                })
            # Do not cascade a second guessed sequence finding from an invalid row.
            previous = None
            last_summary = summary
            continue

        if previous is not None and abs(previous["after"] - before) > EPSILON:
            gap_count += 1
            prev_domain = previous["domain_hint"]
            next_domain = summary["domain_hint"]
            source_evidence = _source_evidence_for_gap(db, previous, summary, uid=uid)
            is_reconciled = source_evidence.get("resolves_gap") is True
            if is_reconciled:
                resolved_gap_count += 1
                classification = "RECONCILED_ALPHA_CONSOLIDATION"
            else:
                unresolved_gap_count += 1
                if prev_domain in {"SLH_HINT", "CREDITS_HINT"} and next_domain in {"SLH_HINT", "CREDITS_HINT"} and prev_domain != next_domain:
                    classification = "POSSIBLE_MIXED_DOMAIN_BOUNDARY"
                elif any(word in (previous["reason"] + " " + summary["reason"]).lower()
                         for word in ("correction", "reset", "test_grant", "zero")):
                    classification = "POSSIBLE_RESET_OR_CORRECTION_BOUNDARY"
                else:
                    classification = "SEQUENCE_GAP_REQUIRES_SOURCE_EVIDENCE"
            if len(findings) < limit:
                findings.append({
                    "type": classification,
                    "reconciled": bool(is_reconciled),
                    "previous": {
                        "index": previous["index"], "time": previous["time"],
                        "reason": previous["reason"], "domain_hint": prev_domain,
                        "after": previous["after"], "order_id": previous["order_id"],
                        "event_id": previous["event_id"],
                        "transfer_id": previous["transfer_id"],
                        "purchase_id": previous["purchase_id"],
                        "idempotency_key": previous["idempotency_key"],
                        "item_id": previous["item_id"],
                    },
                    "next": {
                        "index": summary["index"], "time": summary["time"],
                        "reason": summary["reason"], "domain_hint": next_domain,
                        "before": before, "order_id": summary["order_id"],
                        "event_id": summary["event_id"],
                        "transfer_id": summary["transfer_id"],
                        "purchase_id": summary["purchase_id"],
                        "idempotency_key": summary["idempotency_key"],
                        "item_id": summary["item_id"],
                    },
                    "delta_to_explain": before - previous["after"],
                    "source_evidence_required": not is_reconciled,
                    "source_evidence": source_evidence,
                })

        previous = summary
        last_summary = summary

    tail_matches = (
        current_balance is not None
        and last_summary is not None
        and last_summary["after"] is not None
        and abs(current_balance - last_summary["after"]) <= EPSILON
    )
    blockers = []
    if rows_checked == 0:
        blockers.append("NO_ACCOUNT_LEDGER_ROWS")
    if sequence_rows_checked == 0:
        blockers.append("NO_CREDITS_SEQUENCE_ROWS")
    if arithmetic_count:
        blockers.append("ROW_ARITHMETIC_INVALID")
    if unresolved_gap_count:
        blockers.append("ACCOUNT_LEDGER_SEQUENCE_DISCONTINUITY")
    if malformed_global_rows:
        blockers.append("MALFORMED_GLOBAL_LEDGER_ROW")
    if current_balance is None:
        blockers.append("CURRENT_WALLET_CREDITS_UNREADABLE")
    elif last_summary is None or last_summary["after"] is None:
        blockers.append("LEDGER_TAIL_UNREADABLE")
    elif not tail_matches:
        blockers.append("WALLET_BALANCE_DIFFERS_FROM_LEDGER_TAIL")

    return {
        "scope": "read_only",
        "status": "PASS" if not blockers else "BLOCKED",
        "uid": uid,
        "rows_checked": rows_checked,
        "credits_sequence_rows_checked": sequence_rows_checked,
        "non_credits_rows_skipped": non_credits_rows_skipped,
        "continuity_break_count": unresolved_gap_count,
        "observed_discontinuity_count": gap_count,
        "resolved_gap_count": resolved_gap_count,
        "unresolved_continuity_break_count": unresolved_gap_count,
        "arithmetic_error_count": arithmetic_count,
        "malformed_global_rows": malformed_global_rows,
        "current_wallet_credits": current_balance,
        "ledger_tail_after": last_summary["after"] if last_summary else None,
        "current_balance_matches_tail": bool(tail_matches),
        "finding_count": gap_count + arithmetic_count + malformed_global_rows,
        "blocking_finding_count": unresolved_gap_count + arithmetic_count + malformed_global_rows,
        "findings": findings,
        "findings_truncated": (gap_count + arithmetic_count + malformed_global_rows) > len(findings),
        "blockers": blockers,
        "financial_mutation_performed": False,
        "gate_changed": False,
        "domain_hints_are_authoritative": False,
    }
