import json
import tempfile
import unittest
from pathlib import Path

from core.identity import OWNER_TELEGRAM_ID


class AgentEconomyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        from slh_mcp.agent_economy import AgentEconomyService
        self.economy = AgentEconomyService(root=self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_new_agent_account_starts_at_zero(self):
        self.assertEqual(self.economy.balance("agent-1"), 0)

    def test_treasury_funds_agent_without_touching_user_db(self):
        result = self.economy.treasury_fund(
            agent_id="agent-1",
            amount=100,
            operation_id="fund-1",
            actor=str(OWNER_TELEGRAM_ID),
            reason="bootstrap",
        )
        self.assertEqual(result["status"], "completed")
        self.assertEqual(self.economy.balance("agent-1"), 100)
        self.assertEqual(self.economy.balance("AGENT_TREASURY"), -100)

    def test_transfer_is_idempotent(self):
        self.economy.treasury_fund(
            agent_id="agent-1", amount=100, operation_id="fund-1",
            actor=str(OWNER_TELEGRAM_ID), reason="bootstrap",
        )
        first = self.economy.transfer(
            source_agent="agent-1", target_agent="agent-2", amount=25,
            operation_id="transfer-1", actor=str(OWNER_TELEGRAM_ID), reason="work",
        )
        second = self.economy.transfer(
            source_agent="agent-1", target_agent="agent-2", amount=25,
            operation_id="transfer-1", actor=str(OWNER_TELEGRAM_ID), reason="work",
        )
        self.assertEqual(first["status"], "completed")
        self.assertEqual(second["status"], "duplicate")
        self.assertEqual(self.economy.balance("agent-1"), 75)
        self.assertEqual(self.economy.balance("agent-2"), 25)
        self.assertEqual(len(self.economy.ledger()), 4)

    def test_insufficient_balance_is_rejected_atomically(self):
        with self.assertRaises(ValueError):
            self.economy.transfer(
                source_agent="agent-1", target_agent="agent-2", amount=1,
                operation_id="transfer-x", actor=str(OWNER_TELEGRAM_ID), reason="work",
            )
        self.assertEqual(self.economy.balance("agent-1"), 0)
        self.assertEqual(self.economy.balance("agent-2"), 0)
        self.assertEqual(self.economy.ledger(), [])

    def test_negative_and_zero_amounts_are_rejected(self):
        for amount in (0, -1):
            with self.assertRaises(ValueError):
                self.economy.treasury_fund(
                    agent_id="agent-1", amount=amount, operation_id=f"fund-{amount}",
                    actor=str(OWNER_TELEGRAM_ID), reason="bad",
                )

    def test_operation_ids_are_globally_unique(self):
        self.economy.treasury_fund(
            agent_id="agent-1", amount=10, operation_id="op-1",
            actor=str(OWNER_TELEGRAM_ID), reason="bootstrap",
        )
        with self.assertRaises(ValueError):
            self.economy.treasury_fund(
                agent_id="agent-2", amount=10, operation_id="op-1",
                actor=str(OWNER_TELEGRAM_ID), reason="collision",
            )

    def test_state_is_persistent_and_separate(self):
        self.economy.treasury_fund(
            agent_id="agent-1", amount=7.5, operation_id="fund-1",
            actor=str(OWNER_TELEGRAM_ID), reason="bootstrap",
        )
        path = self.root / "state" / "agent_economy.json"
        self.assertTrue(path.exists())
        document = json.loads(path.read_text(encoding="utf-8"))
        self.assertIn("accounts", document)
        self.assertIn("ledger", document)
        self.assertNotIn("users", document)
        self.assertNotIn("wallet", document)


if __name__ == "__main__":
    unittest.main()
