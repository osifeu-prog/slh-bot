"""Automated, read-only release and owner Credits-ledger audit.

This module reads the canonical state through state_manager.load_db(), emits a
bounded owner-only report, and never writes the database or changes any gate.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
import re
import time
from typing import Any

from core.authority import OWNER_ID


_ALLOWED_STATUSES = {"GREEN", "DEGRADED", "BLOCKED"}
_COMMIT_RE = re.compile(r"^[0-9a-f]{7,64}$", re.IGNORECASE)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _identity() -> dict[str, str]:
    commit = str(
        os.getenv("RAILWAY_GIT_COMMIT_SHA")
        or os.getenv("GIT_COMMIT_SHA")
        or os.getenv("COMMIT_SHA")
        or ""
    ).strip()
    deployment = str(
        os.getenv("RAILWAY_DEPLOYMENT_ID")
        or os.getenv("SLH_DEPLOYMENT_ID")
        or ""
    ).strip()
    return {
        "commit_sha": commit if _COMMIT_RE.fullmatch(commit) else "UNKNOWN",
        "deployment_id": deployment[:120] if deployment else "UNKNOWN",
        "service_id": str(os.getenv("RAILWAY_SERVICE_ID") or "UNKNOWN")[:120],
        "environment_id": str(os.getenv("RAILWAY_ENVIRONMENT_ID") or "UNKNOWN")[:120],
    }


def _safe_text(value: Any, limit: int = 160) -> str:
    return " ".join(str(value if value is not None else "").split())[:limit] or "UNKNOWN"


def _valid_ledger_result(result: Any) -> bool:
    if not isinstance(result, dict):
        return False
    if result.get("scope") != "read_only" or result.get("status") not in {"PASS", "BLOCKED"}:
        return False
    if result.get("financial_mutation_performed") is not False or result.get("gate_changed") is not False:
        return False
    if not isinstance(result.get("findings"), list) or not isinstance(result.get("blockers"), list):
        return False
    for key in (
        "rows_checked",
        "credits_sequence_rows_checked",
        "continuity_break_count",
        "unresolved_continuity_break_count",
        "arithmetic_error_count",
        "malformed_global_rows",
        "blocking_finding_count",
    ):
        value = result.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            return False
    return True


def _valid_release_result(result: Any) -> bool:
    if not isinstance(result, dict) or result.get("overall_status") not in _ALLOWED_STATUSES:
        return False
    checks = result.get("checks")
    return (
        isinstance(checks, dict)
        and all(
            isinstance(item, dict)
            and item.get("status") in _ALLOWED_STATUSES
            and isinstance(item.get("detail"), str)
            for item in checks.values()
        )
    )


def _finding_summary(finding: Any) -> dict[str, Any]:
    if not isinstance(finding, dict):
        return {"type": "MALFORMED_FINDING"}
    previous = finding.get("previous")
    next_row = finding.get("next")
    previous = previous if isinstance(previous, dict) else {}
    next_row = next_row if isinstance(next_row, dict) else {}
    source = finding.get("source_evidence")
    source = source if isinstance(source, dict) else {}
    return {
        "type": _safe_text(finding.get("type"), 90),
        "previous_index": previous.get("index"),
        "previous_reason": _safe_text(previous.get("reason"), 80),
        "next_index": next_row.get("index"),
        "next_reason": _safe_text(next_row.get("reason"), 80),
        "delta_to_explain": finding.get("delta_to_explain"),
        "resolves_gap": source.get("resolves_gap") is True or finding.get("reconciled") is True,
        "source_match_status": _safe_text(source.get("source_match_status"), 100),
    }


def run_once(*, now_utc: str | None = None) -> dict[str, Any]:
    """Build one bounded report from a canonical, read-only state snapshot."""
    started = time.monotonic()
    checked_at = now_utc or _utc_now()
    identity = _identity()
    blockers: list[str] = []
    evidence_integrity = "PASS"
    ledger: dict[str, Any] = {}
    exchange: dict[str, Any] = {}
    release: dict[str, Any] = {}
    database_path = "UNKNOWN"

    if identity["commit_sha"] == "UNKNOWN":
        blockers.append("CODE_COMMIT_IDENTITY_UNAVAILABLE")
        evidence_integrity = "BLOCKED"
    if identity["deployment_id"] == "UNKNOWN":
        blockers.append("DEPLOYMENT_IDENTITY_UNAVAILABLE")
        evidence_integrity = "BLOCKED"

    try:
        import state_manager
        from core.account_ledger_audit import audit_account_ledger
        from core.release_readiness import build_release_report
        from core.system_checks import check_exchange

        database_path = str(getattr(state_manager, "DB_FILE", "state/db.json"))
        db = state_manager.load_db()
        if not isinstance(db, dict):
            raise TypeError("DB_ROOT_INVALID")
        if not isinstance(db.get("users"), dict) or not isinstance(db.get("ledger"), list):
            raise TypeError("DB_SCHEMA_INCOMPLETE")
        if "transactions" not in db:
            raise TypeError("DB_SCHEMA_INCOMPLETE")

        ledger_raw = audit_account_ledger(db, OWNER_ID)
        release_raw = build_release_report(db=db)
        exchange_raw = check_exchange(db)

        if not _valid_ledger_result(ledger_raw):
            blockers.append("ACCOUNT_LEDGER_AUDIT_RESULT_INVALID")
            evidence_integrity = "BLOCKED"
        else:
            ledger = ledger_raw
            if ledger["status"] != "PASS" or ledger["blocking_finding_count"] != 0:
                ledger_blockers = [
                    _safe_text(item, 100)
                    for item in ledger.get("blockers", [])[:8]
                    if item is not None
                ]
                blockers.extend(ledger_blockers or ["ACCOUNT_LEDGER_NOT_PASS"])
            if ledger.get("findings_truncated") is True:
                blockers.append("ACCOUNT_LEDGER_FINDINGS_TRUNCATED")

        if not _valid_release_result(release_raw):
            blockers.append("RELEASE_READINESS_RESULT_INVALID")
            evidence_integrity = "BLOCKED"
        else:
            release = release_raw
            if release["overall_status"] == "BLOCKED":
                release_blockers = [
                    _safe_text(item, 150)
                    for item in release.get("blockers", [])[:8]
                    if item is not None
                ]
                blockers.extend(release_blockers or ["RELEASE_READINESS_BLOCKED"])

        if not isinstance(exchange_raw, dict):
            blockers.append("EXCHANGE_AUDIT_RESULT_INVALID")
            evidence_integrity = "BLOCKED"
        else:
            exchange = exchange_raw
            if exchange.get("public_gate") != "CLOSED":
                blockers.append("PUBLIC_EXCHANGE_GATE_NOT_CLOSED")
            if exchange.get("account_ledger_status") != "PASS" or exchange.get("account_ledger_integrity") is not True:
                blockers.append("EXCHANGE_ACCOUNT_LEDGER_NOT_PASS")
            if exchange.get("verdict") == "BLOCKED":
                blockers.append("EXCHANGE_VERDICT_BLOCKED")
    except Exception as exc:
        blockers.append(f"AUDIT_SNAPSHOT_UNAVAILABLE:{type(exc).__name__}")
        evidence_integrity = "BLOCKED"

    blockers = list(dict.fromkeys(_safe_text(item, 180) for item in blockers))
    release_status = str(release.get("overall_status") or "BLOCKED").upper()
    ledger_status = str(ledger.get("status") or "BLOCKED").upper()
    exchange_status = str(exchange.get("verdict") or "BLOCKED").upper()
    public_gate = str(exchange.get("public_gate") or "UNKNOWN").upper()

    if evidence_integrity != "PASS" or blockers or release_status == "BLOCKED" or ledger_status != "PASS":
        overall_status = "BLOCKED"
    elif release_status != "GREEN" or public_gate == "CLOSED":
        overall_status = "DEGRADED"
    else:
        overall_status = "PASS"

    elapsed_ms = max(0, int((time.monotonic() - started) * 1000))
    return {
        "schema_version": 1,
        "checked_at_utc": checked_at,
        "finished_at_utc": _utc_now(),
        "duration_ms": elapsed_ms,
        "status": overall_status,
        "evidence_integrity": evidence_integrity,
        "source": {
            **identity,
            "database_path": database_path,
            "database_source": "state_manager.load_db",
        },
        "ledger": {
            "status": ledger_status,
            "rows_checked": ledger.get("rows_checked", 0),
            "credits_sequence_rows_checked": ledger.get("credits_sequence_rows_checked", 0),
            "continuity_break_count": ledger.get("continuity_break_count", 0),
            "unresolved_continuity_break_count": ledger.get("unresolved_continuity_break_count", 0),
            "arithmetic_error_count": ledger.get("arithmetic_error_count", 0),
            "malformed_global_rows": ledger.get("malformed_global_rows", 0),
            "current_balance_matches_tail": ledger.get("current_balance_matches_tail") is True,
            "findings": [
                _finding_summary(item)
                for item in ledger.get("findings", [])[:8]
            ] if isinstance(ledger.get("findings"), list) else [],
            "findings_truncated": ledger.get("findings_truncated") is True,
        },
        "exchange": {
            "verdict": exchange_status,
            "public_gate": public_gate,
            "public_ready": exchange.get("public_ready") is True,
            "account_ledger_status": str(exchange.get("account_ledger_status") or "UNKNOWN"),
            "account_ledger_integrity": exchange.get("account_ledger_integrity") is True,
        },
        "release_readiness": {
            "status": release_status,
            "checks": {
                str(name)[:80]: {
                    "status": str(item.get("status") or "BLOCKED"),
                    "detail": _safe_text(item.get("detail"), 180),
                }
                for name, item in release.get("checks", {}).items()
                if isinstance(item, dict)
            } if isinstance(release.get("checks"), dict) else {},
        },
        "blockers": blockers[:16],
        "evidence_refs": [
            "/check_owner_ledger",
            "/go_live_report",
            "https://github.com/osifeu-prog/slh-bot/issues/863",
        ],
        "financial_mutation_performed": False,
        "gate_changed": False,
    }


def render_report(report: Any) -> str:
    """Render a short owner-facing summary without exposing other accounts."""
    if not isinstance(report, dict):
        return "⛔ AUTOMATED RELEASE AUDIT — BLOCKED\nInvalid audit result. No changes were made."
    source = report.get("source") if isinstance(report.get("source"), dict) else {}
    ledger = report.get("ledger") if isinstance(report.get("ledger"), dict) else {}
    exchange = report.get("exchange") if isinstance(report.get("exchange"), dict) else {}
    release = report.get("release_readiness") if isinstance(report.get("release_readiness"), dict) else {}
    lines = [
        "🧭 SLH AUTOMATED RELEASE AUDIT — READ ONLY",
        "",
        f"Checked (UTC): {_safe_text(report.get('checked_at_utc'), 40)}",
        f"Overall: {_safe_text(report.get('status'), 20)} · evidence integrity={_safe_text(report.get('evidence_integrity'), 20)}",
        f"Code commit: {_safe_text(source.get('commit_sha'), 64)}",
        f"Deployment: {_safe_text(source.get('deployment_id'), 120)}",
        f"Canonical DB source: {_safe_text(source.get('database_source'), 40)} · {_safe_text(source.get('database_path'), 120)}",
        "",
        f"Owner Credits ledger: {_safe_text(ledger.get('status'), 20)} · unresolved gaps={ledger.get('unresolved_continuity_break_count', 'UNKNOWN')} · arithmetic errors={ledger.get('arithmetic_error_count', 'UNKNOWN')}",
        f"Exchange: verdict={_safe_text(exchange.get('verdict'), 30)} · public gate={_safe_text(exchange.get('public_gate'), 20)} · ledger={_safe_text(exchange.get('account_ledger_status'), 20)}",
        f"Release readiness: {_safe_text(release.get('status'), 20)}",
    ]
    findings = ledger.get("findings") if isinstance(ledger.get("findings"), list) else []
    for finding in findings[:4]:
        if not isinstance(finding, dict):
            continue
        lines.append(
            "Finding: "
            f"{_safe_text(finding.get('type'), 70)} · "
            f"rows #{_safe_text(finding.get('previous_index'), 12)} → #{_safe_text(finding.get('next_index'), 12)} · "
            f"{_safe_text(finding.get('source_match_status'), 75)} · "
            f"resolves_gap={finding.get('resolves_gap') is True}"
        )
    if report.get("blockers"):
        lines.append("")
        lines.append("Blockers:")
        for blocker in report["blockers"][:8]:
            lines.append("• " + _safe_text(blocker, 170))
    if report.get("evidence_refs"):
        lines.append("")
        lines.append("Evidence: " + " · ".join(_safe_text(item, 110) for item in report["evidence_refs"][:3]))
    lines += [
        "",
        "🔒 No DB, ledger, Credits, wallets, orders, or gates were changed.",
        "Trading remains subject to the existing separate opening authorization.",
    ]
    return "\n".join(lines)[:3900]


def _signature(report: dict[str, Any]) -> str:
    payload = {
        "status": report.get("status"),
        "evidence_integrity": report.get("evidence_integrity"),
        "ledger": report.get("ledger"),
        "exchange": report.get("exchange"),
        "release": report.get("release_readiness"),
        "blockers": report.get("blockers"),
        "source": report.get("source"),
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _deliver_if_changed(report, bot, log, last_signature=None, last_status=None):
    signature = _signature(report)
    status = str(report.get("status") or "BLOCKED")
    should_notify = signature != last_signature and (
        status != "PASS" or (last_status is not None and last_status != "PASS")
    )
    if should_notify:
        try:
            bot.send_message(chat_id=int(OWNER_ID), text=render_report(report), parse_mode=None)
            log(
                "[SLH_RELEASE_AUDIT] owner_notification=sent "
                f"status={_safe_text(status, 20)} signature={signature[:12]}"
            )
        except Exception as exc:
            log(
                "[SLH_RELEASE_AUDIT] owner_notification=failed "
                f"status={_safe_text(status, 20)} error={type(exc).__name__}"
            )
            return last_signature, last_status
    return signature, status


def run_periodic(bot, log, interval_seconds=None) -> None:
    """Run immediately, then periodically; notify owner only when status changes."""
    try:
        configured = int(
            interval_seconds
            if interval_seconds is not None
            else os.getenv("SLH_RELEASE_AUDIT_INTERVAL_SECONDS", "900")
        )
    except (TypeError, ValueError, OverflowError):
        configured = 900
    interval = max(60, configured)
    last_signature = None
    last_status = None
    while True:
        try:
            report = run_once()
            summary = {
                "checked_at_utc": report.get("checked_at_utc"),
                "status": report.get("status"),
                "evidence_integrity": report.get("evidence_integrity"),
                "commit_sha": (report.get("source") or {}).get("commit_sha"),
                "deployment_id": (report.get("source") or {}).get("deployment_id"),
                "ledger_status": (report.get("ledger") or {}).get("status"),
                "unresolved_gaps": (report.get("ledger") or {}).get("unresolved_continuity_break_count"),
                "exchange_verdict": (report.get("exchange") or {}).get("verdict"),
                "public_gate": (report.get("exchange") or {}).get("public_gate"),
                "blocker_count": len(report.get("blockers") or []),
            }
            log("[SLH_RELEASE_AUDIT] " + json.dumps(summary, sort_keys=True, separators=(",", ":")))
            last_signature, last_status = _deliver_if_changed(
                report, bot, log, last_signature, last_status
            )
        except Exception as exc:
            log(f"[SLH_RELEASE_AUDIT] status=BLOCKED error={type(exc).__name__}")
        time.sleep(interval)
