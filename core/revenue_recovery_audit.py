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
            if not any(term in low for term in REVENUE_FIELDS):
                if not any(name.lower() in low for name in TARGET_SNAPSHOTS):
                    continue
            records += 1
            if any(term in low for term in REVENUE_FIELDS):
                dist_refs += 1
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
    lines.append("VERDICT: HISTORICAL PAYOUT AMOUNTS NOT RECONSTRUCTED")
    lines.append("Next safe step: inspect independent snapshots/exports before any repair.")
    return lines


def format_revenue_recovery_report(root="."):
    """Format the report within Telegram's conservative message-size limit."""
    lines = build_revenue_recovery_report(root)
    text = "\n".join(lines)
    return text[:3800]
