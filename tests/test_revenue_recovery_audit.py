"""Tests for the read-only revenue recovery report."""
import json
from datetime import datetime, timezone
from pathlib import Path

from core.revenue_recovery_audit import (
    build_revenue_recovery_report,
    format_revenue_recovery_report,
)


def _epoch(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def test_report_summarizes_current_state_and_historical_reset(tmp_path):
    state = tmp_path / "state"
    backups = state / "backups"
    backups.mkdir(parents=True)
    db_path = state / "db.json"
    db = {
        "users": {
            "u1": {"wallet": {"revenue_share_claimable": 0}},
            "u2": {"wallet": {"revenue_share_claimable": 0}},
        },
        "revenue_distributions": {},
        "revenue_share_pool": {
            "last_distribution": None,
            "total_distributed": 0,
            "surplus_accumulated": 0,
        },
        "stake_positions": {
            "p1": {"total_received": 0},
            "p2": {"total_received": 0},
        },
    }
    original = json.dumps(db, ensure_ascii=False).encode()
    db_path.write_bytes(original)
    (state / "exec_audit.json").write_text(
        json.dumps([
            {
                "time": _epoch("2026-10-05T16:27:03.783835Z"),
                "source": "e",
                "result": "exit_0",
                "cmd": (
                    'w["revenue_share_claimable"] = 0; '
                    'd["revenue_share_pool"] = {"total_distributed": 0}; '
                    'd["revenue_distributions"] = {}'
                ),
            },
            {
                "time": _epoch("2026-10-05T18:30:13.399395Z"),
                "source": "e",
                "result": "exit_0",
                "cmd": 'open("state/backups/db_20261005T152922.733019Z.json")',
            },
        ]),
        encoding="utf-8",
    )

    report = build_revenue_recovery_report(tmp_path)
    joined = "\n".join(report)

    assert "CANONICAL DB: OK" in joined
    assert "CURRENT DISTRIBUTION KEYS: 0" in joined
    assert "USERS WITH NONZERO CLAIMABLE: 0" in joined
    assert "Explicit combined distribution reset commands: 1" in joined
    assert "Audit references to db_20261005T152922.733019Z.json: 1" in joined
    assert "HISTORICAL PAYOUT AMOUNTS NOT RECONSTRUCTED" in joined
    assert db_path.read_bytes() == original


def test_report_handles_missing_or_invalid_db_without_writes(tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    report_missing = "\n".join(build_revenue_recovery_report(tmp_path))
    assert "CANONICAL DB: MISSING" in report_missing

    (state / "db.json").write_text("{not-json", encoding="utf-8")
    report_invalid = "\n".join(build_revenue_recovery_report(tmp_path))
    assert "CANONICAL DB: INVALID:JSONDecodeError" in report_invalid


def test_telegram_report_is_bounded(tmp_path):
    (tmp_path / "state").mkdir()
    text = format_revenue_recovery_report(tmp_path)
    assert len(text) <= 3800
    assert "READ ONLY" in text
