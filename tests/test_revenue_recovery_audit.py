"""Tests for the read-only revenue recovery report."""
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from core.revenue_recovery_audit import (
    build_revenue_recovery_report,
    format_revenue_recovery_report,
)


def _epoch(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


class RevenueRecoveryAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.state = self.root / "state"
        self.state.mkdir()
        (self.state / "backups").mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def test_report_summarizes_current_state_and_historical_reset(self):
        db_path = self.state / "db.json"
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
        (self.state / "exec_audit.json").write_text(
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

        report = "\n".join(build_revenue_recovery_report(self.root))
        self.assertIn("CANONICAL DB: OK", report)
        self.assertIn("CURRENT DISTRIBUTION KEYS: 0", report)
        self.assertIn("USERS WITH NONZERO CLAIMABLE: 0", report)
        self.assertIn("Explicit combined distribution reset commands: 1", report)
        self.assertIn("Audit references to db_20261005T152922.733019Z.json: 1", report)
        self.assertIn("HISTORICAL PAYOUT AMOUNTS NOT RECONSTRUCTED", report)
        self.assertEqual(db_path.read_bytes(), original)

    def test_report_handles_missing_or_invalid_db_without_writes(self):
        report_missing = "\n".join(build_revenue_recovery_report(self.root))
        self.assertIn("CANONICAL DB: MISSING", report_missing)

        (self.state / "db.json").write_text("{not-json", encoding="utf-8")
        report_invalid = "\n".join(build_revenue_recovery_report(self.root))
        self.assertIn("CANONICAL DB: INVALID:JSONDecodeError", report_invalid)

    def test_telegram_report_is_bounded(self):
        text = format_revenue_recovery_report(self.root)
        self.assertLessEqual(len(text), 3800)
        self.assertIn("READ ONLY", text)


if __name__ == "__main__":
    unittest.main()
