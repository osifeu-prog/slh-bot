"""Read-only diagnostics for a single user's canonical Credits ledger sequence.

This module reports inconsistencies; it never repairs, rewrites, or classifies a
ledger event as valid financial evidence. Domain hints are heuristic labels from
the reason string and must be corroborated against source events before use.
"""
from __future__ import annotations

import math
from typing import Any

EPSILON = 1e-8
MAX_FINDINGS = 25


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
    """Prefer explicit asset/domain metadata; only skip non-Credits rows with source markers."""
    meta = row.get("meta")
    meta = meta if isinstance(meta, dict) else {}
    explicit = str(meta.get("ledger_domain") or meta.get("asset") or "").strip().lower()
    if explicit:
        if "slh" in explicit or "token" in explicit:
            return "SLH_HINT"
        if "credit" in explicit:
            return "CREDITS_HINT"

    # This exact reconciliation event documents a staked-counter resync, not a
    # Credits-wallet transaction. Require both counter fields and the explicit
    # "no credits minted" source note; the reason string alone is not proof.
    reason = str(row.get("reason") or "").strip().lower()
    note = str(meta.get("note") or "").strip().lower()
    if (
        reason == "reconciliation:staked_counter_fix"
        and "staked_before" in meta
        and "staked_after" in meta
        and "no credits minted" in note
    ):
        return "NON_CREDITS_HINT"

    return _reason_domain_hint(row.get("reason"))


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
    }


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
        # This report validates the user's Credits sequence. SLH-token rows and
        # explicitly source-marked non-Credits rows must not be compared with
        # the Credits wallet. Keep the previous Credits candidate across these
        # rows so genuine Credits discontinuities cannot be hidden.
        if summary["domain_hint"] in {"SLH_HINT", "NON_CREDITS_HINT"}:
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
                    "previous": {
                        "index": previous["index"], "time": previous["time"],
                        "reason": previous["reason"], "domain_hint": prev_domain,
                        "after": previous["after"], "order_id": previous["order_id"],
                        "event_id": previous["event_id"],
                    },
                    "next": {
                        "index": summary["index"], "time": summary["time"],
                        "reason": summary["reason"], "domain_hint": next_domain,
                        "before": before, "order_id": summary["order_id"],
                        "event_id": summary["event_id"],
                    },
                    "delta_to_explain": before - previous["after"],
                    "source_evidence_required": True,
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
    if gap_count:
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
        "continuity_break_count": gap_count,
        "arithmetic_error_count": arithmetic_count,
        "malformed_global_rows": malformed_global_rows,
        "current_wallet_credits": current_balance,
        "ledger_tail_after": last_summary["after"] if last_summary else None,
        "current_balance_matches_tail": bool(tail_matches),
        "finding_count": gap_count + arithmetic_count + malformed_global_rows,
        "findings": findings,
        "findings_truncated": (gap_count + arithmetic_count + malformed_global_rows) > len(findings),
        "blockers": blockers,
        "financial_mutation_performed": False,
        "gate_changed": False,
        "domain_hints_are_authoritative": False,
    }
