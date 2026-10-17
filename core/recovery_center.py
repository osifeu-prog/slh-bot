"""Unified, read-only recovery guidance built from canonical SLH checks.

This module classifies known blockers and links them to existing evidence. It
never repairs balances, writes recovery state, or changes financial gates.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any


def _fingerprint(kind: str, *parts: Any) -> str:
    """Stable identity for the same observed finding across repeated reports."""
    payload = json.dumps([kind, *parts], sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16].upper()


def _gap_blocker(finding: dict) -> dict:
    previous = finding.get("previous") if isinstance(finding.get("previous"), dict) else {}
    next_row = finding.get("next") if isinstance(finding.get("next"), dict) else {}
    delta = finding.get("delta_to_explain")
    finding_type = str(finding.get("type") or "SEQUENCE_GAP_REQUIRES_SOURCE_EVIDENCE")
    fingerprint = _fingerprint(
        finding_type,
        previous.get("index"),
        next_row.get("index"),
        previous.get("reason"),
        next_row.get("reason"),
        delta,
    )
    return {
        "id": "LEDGER-" + fingerprint,
        "kind": finding_type,
        "status": "BLOCKED",
        "summary": (
            f"Credits ledger gap between row {previous.get('index', '?')} "
            f"({previous.get('reason', 'UNKNOWN')}) and row "
            f"{next_row.get('index', '?')} ({next_row.get('reason', 'UNKNOWN')})."
        ),
        "evidence": {
            "previous": previous,
            "next": next_row,
            "delta_to_explain": delta,
            "source_evidence": finding.get("source_evidence", {}),
        },
        "next_action": (
            "Locate independent source evidence for the missing balance transition; "
            "compare the linked transaction/order/audit records. Do not insert a "
            "synthetic ledger row or reset the audit."
        ),
        "automatic_fix": "NOT_SAFE_WITHOUT_SOURCE_EVIDENCE",
        "human_action_required": True,
    }


def build_recovery_center_report(*, release_report=None, db=None) -> dict:
    """Return a deterministic recovery plan from existing read-only checks."""
    from core.release_readiness import build_release_report
    import state_manager
    from core.authority import OWNER_ID
    from core.account_ledger_audit import audit_account_ledger

    report = release_report if isinstance(release_report, dict) else build_release_report()
    if db is None:
        db = state_manager.load_db()

    audit = audit_account_ledger(db, str(OWNER_ID))
    blockers = []
    findings = audit.get("findings", []) if isinstance(audit, dict) else []
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        if finding.get("source_evidence_required") is True or str(finding.get("type", "")).startswith(
            ("SEQUENCE_", "POSSIBLE_", "RECONCILED_")
        ):
            if finding.get("reconciled") is not True:
                blockers.append(_gap_blocker(finding))

    # The canonical exchange check can fail for reasons other than a ledger gap.
    exchange = report.get("checks", {}).get("Internal exchange", {})
    exchange_detail = str(exchange.get("detail") or "")
    if exchange.get("status") == "BLOCKED" and "ACCOUNT_LEDGER_SEQUENCE_DISCONTINUITY" in exchange_detail and not blockers:
        blockers.append({
            "id": "EXCHANGE-ACCOUNT_LEDGER_SEQUENCE_DISCONTINUITY",
            "kind": "ACCOUNT_LEDGER_SEQUENCE_DISCONTINUITY",
            "status": "BLOCKED",
            "summary": "Exchange readiness is blocked by the owner account ledger continuity audit.",
            "evidence": {
                "audit_status": audit.get("status"),
                "continuity_break_count": audit.get("continuity_break_count"),
                "unresolved_continuity_break_count": audit.get("unresolved_continuity_break_count"),
                "findings": findings[:5],
            },
            "next_action": (
                "Inspect the exact previous/next ledger rows returned by the account audit "
                "and locate independent source evidence before considering reconciliation."
            ),
            "automatic_fix": "NOT_SAFE_WITHOUT_SOURCE_EVIDENCE",
            "human_action_required": True,
        })

    settlement = report.get("checks", {}).get("External settlement gates", {})
    settlement_detail = str(settlement.get("detail") or "")
    review_items = []
    if "BNB empirical settlement evidence is revalidated" in settlement_detail or (
        "BNB empirical proof revalidated" in settlement_detail
    ):
        review_items.append({
            "id": "BNB-OPERATOR-GATE-REVIEW",
            "kind": "INTENTIONAL_GATE_CLOSED_EVIDENCE_READY",
            "status": "REVIEW_REQUIRED",
            "summary": "BNB evidence is ready, but the public deposit gate remains closed.",
            "evidence": {"release_check": settlement_detail},
            "next_action": (
                "Keep the gate closed until the operator independently reviews the current "
                "evidence and makes a separate opening decision."
            ),
            "automatic_fix": "NEVER_OPEN_GATE_AUTOMATICALLY",
            "human_action_required": True,
        })

    return {
        "mode": "READ_ONLY",
        "overall_status": "BLOCKED" if blockers else ("REVIEW_REQUIRED" if review_items else "NO_KNOWN_RECOVERY_BLOCKERS"),
        "blockers": blockers,
        "review_items": review_items,
        "account_ledger": {
            "status": audit.get("status"),
            "rows_checked": audit.get("rows_checked"),
            "continuity_break_count": audit.get("continuity_break_count"),
            "unresolved_continuity_break_count": audit.get("unresolved_continuity_break_count"),
            "current_balance_matches_tail": audit.get("current_balance_matches_tail"),
        },
        "release_status": report.get("overall_status", "UNKNOWN"),
        "safety": [
            "No balance or ledger writes",
            "No BNB/TON/Exchange gate changes",
            "No synthetic reconciliation",
        ],
        "persistence": (
            "Finding IDs are deterministic; lifecycle history is not persisted by this "
            "read-only version. A blocker is not considered resolved until canonical "
            "evidence proves it."
        ),
    }
