"""Read-only forensic report for historical Revenue Share recovery.

This module deliberately reads files directly rather than using state_manager,
whose load_db() starts a periodic backup scheduler. It never writes state,
ledger entries, audit records, or backup files.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path


PERIOD_START = datetime(2026, 10, 5, tzinfo=timezone.utc).timestamp()
PERIOD_END = datetime(2026, 10, 6, tzinfo=timezone.utc).timestamp()
TARGET_SNAPSHOTS = (
    "db_20261005T152922.733019Z.json",
    "db_pre_cleanup_20261005T183427Z.json",
)
REVENUE_FIELDS = (
    "revenue_distributions",
    "revenue_share_pool",
    "revenue_share_claimable",
)
AUDIT_MATCH_TERMS = REVENUE_FIELDS + (
    "distribute_revenue",
    "total_received",
    "test-2026-10-05",
    "2026-w40-real",
)
_ENGINE_CALL_RE = re.compile(r"\\bdistribute_revenue\\s*\\(", re.IGNORECASE)
_DELETE_OR_MOVE_RE = re.compile(
    r"(?:os\.remove\s*\(|\.unlink\s*\(|rmtree\s*\(|"
    r"shutil\.move\s*\(|os\.rename\s*\(|"
    r"\brm\s+-[rf]+\b|\bmv\s+)",
    re.IGNORECASE,
)


def _decimal(value):
    try:
        return Decimal(str(value or 0))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def _read_json(path):
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle), "OK"
    except FileNotFoundError:
        return None, "MISSING"
    except Exception as exc:
        return None, "INVALID:" + type(exc).__name__


def _event_epoch(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _audit_paths(root):
    return (
        root / "state" / "exec_audit.json",
        root / "state" / "exec_audit_archive.json",
    )


def build_revenue_recovery_report(root="."):
    """Return a bounded report. This function is read-only."""
    root = Path(root)
    lines = [
        "SLH REVENUE RECOVERY AUDIT",
        "Mode: READ ONLY — no state or ledger writes",
        "Historical window: 2026-10-05 UTC",
        "",
    ]

    db_path = root / "state" / "db.json"
    db, db_status = _read_json(db_path)
    lines.append("CANONICAL DB: " + db_status)

    if isinstance(db, dict):
        distributions = db.get("revenue_distributions", {})
        if not isinstance(distributions, dict):
            distributions = {}
            lines.append("Warning: revenue_distributions has unexpected type")
        pool = db.get("revenue_share_pool", {})
        if not isinstance(pool, dict):
            pool = {}

        claimable_values = []
        users = db.get("users", {})
        if isinstance(users, dict):
            for user in users.values():
                if not isinstance(user, dict):
                    continue
                wallet = user.get("wallet", {})
                if not isinstance(wallet, dict):
                    continue
                amount = _decimal(wallet.get("revenue_share_claimable", 0))
                if amount != 0:
                    claimable_values.append(amount)

        positions = db.get("stake_positions", {})
        if not isinstance(positions, dict):
            positions = {}
        received_values = [
            _decimal(pos.get("total_received", 0))
            for pos in positions.values()
            if isinstance(pos, dict)
        ]
        nonzero_received = [amount for amount in received_values if amount != 0]

        ledger_marker_rows = []
        ledger = db.get("ledger", [])
        if isinstance(ledger, list):
            for entry in ledger:
                if not isinstance(entry, dict):
                    continue
                reason = str(entry.get("reason") or "").lower()
                meta = entry.get("meta") or {}
                try:
                    meta_text = json.dumps(meta, ensure_ascii=False, sort_keys=True).lower()
                except (TypeError, ValueError):
                    meta_text = ""
                marker_text = reason + " " + meta_text
                if any(token in marker_text for token in (
                    "revenue_share", "revenue share",
                    "revenue_distribution", "revenue distribution",
                )):
                    ledger_marker_rows.append(entry)

        lines.extend([
            "CURRENT DISTRIBUTION KEYS: " + str(len(distributions)),
            "CURRENT POOL total_distributed: "
            + format(_decimal(pool.get("total_distributed")), "f"),
            "CURRENT POOL surplus_accumulated: "
            + format(_decimal(pool.get("surplus_accumulated")), "f"),
            "USERS WITH NONZERO CLAIMABLE: " + str(len(claimable_values)),
            "TOTAL CLAIMABLE: " + format(sum(claimable_values, Decimal("0")), "f"),
            "POSITIONS WITH NONZERO total_received: " + str(len(nonzero_received)),
            "SUM POSITION total_received: "
            + format(sum(nonzero_received, Decimal("0")), "f"),
            "LEDGER ROWS TAGGED REVENUE-SHARE/DISTRIBUTION: "
            + str(len(ledger_marker_rows)),
        ])
        if distributions:
            lines.append(
                "CURRENT PERIOD LABELS: "
                + ", ".join(sorted(str(k)[:55] for k in distributions)[:8])
            )
        if not distributions and not claimable_values and not nonzero_received:
            lines.append(
                "ASSESSMENT: current DB has no retained distribution/claimable "
                "snapshot; this does not prove that no historical payout occurred."
            )
    else:
        lines.append("ASSESSMENT: canonical DB could not be inspected.")

    lines.append("")
    lines.append("BACKUP INVENTORY (known state paths only):")
    backup_roots = (
        root / "state" / "backups",
        root / "state" / "takeover" / "backups",
    )
    available = []
    for folder in backup_roots:
        if not folder.is_dir():
            lines.append(folder.as_posix().replace(root.as_posix() + "/", "") + ": MISSING_DIR")
            continue
        files = sorted(
            (p for p in folder.glob("db_*.json") if p.is_file()),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        lines.append(
            folder.as_posix().replace(root.as_posix() + "/", "")
            + ": "
            + str(len(files))
            + " db_*.json file(s)"
        )
        for path in files:
            name = path.name
            if (
                "20261005" in name
                or "152922" in name
                or "pre_cleanup" in name
            ):
                available.append(name)

    lines.append("OCT-05 / PRE-CLEANUP NAMED COPIES: " + (
        ", ".join(sorted(set(available))) if available else "NONE IN KNOWN BACKUP PATHS"
    ))
    for filename in TARGET_SNAPSHOTS:
        exists = any((folder / filename).is_file() for folder in backup_roots)
        lines.append("TARGET " + filename + ": " + ("FOUND" if exists else "MISSING"))

    lines.append("")
    lines.append("EXEC AUDIT EVIDENCE (classified; raw commands not printed):")
    records = 0
    dist_refs = 0
    reset_refs = 0
    snapshot_refs = {name: 0 for name in TARGET_SNAPSHOTS}
    engine_refs = 0
    engine_calls = 0
    engine_call_times = []
    test_period_refs = 0
    real_period_refs = 0
    total_received_refs = 0
    file_ops = 0
    file_op_times = []
    audit_status = []
    for path in _audit_paths(root):
        data, status = _read_json(path)
        audit_status.append(path.name + "=" + status)
        if not isinstance(data, list):
            continue
        for row in data:
            if not isinstance(row, dict):
                continue
            timestamp = _event_epoch(row.get("time"))
            if not (PERIOD_START <= timestamp < PERIOD_END):
                continue
            cmd = str(row.get("cmd") or "")
            low = cmd.lower()
            if not any(term in low for term in AUDIT_MATCH_TERMS):
                if not any(name.lower() in low for name in TARGET_SNAPSHOTS):
                    continue
            records += 1
            if any(term in low for term in REVENUE_FIELDS):
                dist_refs += 1
            calls_in_command = len(_ENGINE_CALL_RE.findall(low))
            if "distribute_revenue" in low:
                engine_refs += 1
            if calls_in_command:
                engine_calls += calls_in_command
                engine_call_times.append((
                    timestamp,
                    str(row.get("result") or "unknown"),
                    calls_in_command,
                ))
            if "test-2026-10-05" in low:
                test_period_refs += 1
            if "2026-w40-real" in low:
                real_period_refs += 1
            if "total_received" in low:
                total_received_refs += 1
            if (
                "revenue_distributions" in low
                and re.search(r"revenue_distributions[^\n]{0,20}=\s*\{\s*\}", low)
                and "revenue_share_pool" in low
                and "revenue_share_claimable" in low
            ):
                reset_refs += 1
            for name in TARGET_SNAPSHOTS:
                if name.lower() in low:
                    snapshot_refs[name] += 1
            if _DELETE_OR_MOVE_RE.search(low) and (
                "backup" in low
                or "db.json" in low
                or any(name.lower() in low for name in TARGET_SNAPSHOTS)
            ):
                file_ops += 1
                file_op_times.append(timestamp)

    lines.append("Audit files: " + ", ".join(audit_status))
    lines.append("Matching Oct-05 evidence records: " + str(records))
    lines.append("Revenue-field references: " + str(dist_refs))
    lines.append("Distribution engine references: " + str(engine_refs))
    lines.append("Explicit distribute_revenue(...) call expressions: " + str(engine_calls))
    lines.append("Audit records with test-2026-10-05 label: " + str(test_period_refs))
    lines.append("Audit records with 2026-W40-real label: " + str(real_period_refs))
    lines.append("Audit records referencing total_received: " + str(total_received_refs))
    if engine_call_times:
        details = []
        for timestamp, result, count in engine_call_times[:6]:
            dt = datetime.fromtimestamp(timestamp, timezone.utc).isoformat()
            details.append(dt + " result=" + result + " calls=" + str(count))
        lines.append("Engine call records UTC (command exit is not payout proof): " + " | ".join(details))
    lines.append("Explicit combined distribution reset commands: " + str(reset_refs))
    for name, count in snapshot_refs.items():
        lines.append("Audit references to " + name + ": " + str(count))
    lines.append(
        "Recorded backup/delete/move commands matching scoped patterns: "
        + str(file_ops)
    )
    if file_op_times:
        latest = datetime.fromtimestamp(max(file_op_times), timezone.utc).isoformat()
        lines.append("Latest matching file-operation record UTC: " + latest)
    lines.append(
        "Note: no matching command record is not proof that no file was removed; "
        "this report searches only the available exec audit files."
    )
    lines.append("")
    lines.append("VERDICT: HISTORICAL DISTRIBUTION/ACCRUAL AMOUNTS NOT RECONSTRUCTED")
    lines.append(
        "Important: Revenue Share engine calls update internal claimable fields; "
        "these records alone do not prove a Credits transfer or cash payout."
    )
    lines.append("Next safe step: inspect independent snapshots/exports before any repair.")
    return lines


def format_revenue_recovery_report(root="."):
    """Format the report within Telegram's conservative message-size limit."""
    lines = build_revenue_recovery_report(root)
    text = "\n".join(lines)
    return text[:3800]
