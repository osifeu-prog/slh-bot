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
            "ledger": [
                {"reason": "revenue_share:claimable", "amount": 2.5, "meta": {}}
            ],
        }
        original = json.dumps(db, ensure_ascii=False).encode()
        db_path.write_bytes(original)
        backup_path = self.state / "backups" / "db_snapshot_fixture.json"
        snapshot = {
            "users": {"u1": {"wallet": {"revenue_share_claimable": 3}}},
            "revenue_distributions": {"fixture-period": {"total_distributed": 2}},
            "revenue_share_pool": {"total_distributed": 2, "surplus_accumulated": 1},
            "stake_positions": {"p1": {"total_received": 4}},
        }
        snapshot_bytes = json.dumps(snapshot, ensure_ascii=False).encode()
        backup_path.write_bytes(snapshot_bytes)
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
                    "time": _epoch("2026-10-05T16:25:00Z"),
                    "source": "e",
                    "result": "exit_0",
                    "cmd": (
                        'from core.staking_revenue_share import distribute_revenue; '
                        'result = distribute_revenue(Decimal("50"), Decimal("5"), "2026-W40-real")'
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
        self.assertIn("Explicit distribute_revenue(...) call expressions: 1", report)
        self.assertIn(
            "gross=50 costs=5 period=2026-W40-real",
            report,
        )
        self.assertIn(
            "SNAPSHOT db_snapshot_fixture.json: distributions=1 pool_total_distributed=2 "
            "claimable_users=1 claimable_total=3 positions_received=1 positions_received_total=4",
            report,
        )
        self.assertIn("Audit records with 2026-W40-real label: 1", report)
        self.assertIn("LEDGER ROWS TAGGED REVENUE-SHARE/DISTRIBUTION: 1", report)
        self.assertIn("HISTORICAL DISTRIBUTION/ACCRUAL AMOUNTS NOT RECONSTRUCTED", report)
        self.assertIn("do not prove a Credits transfer or cash payout", report)
        self.assertEqual(db_path.read_bytes(), original)
        self.assertEqual(backup_path.read_bytes(), snapshot_bytes)

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
