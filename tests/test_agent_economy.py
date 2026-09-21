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

    def test_revenue_funds_treasury_and_agent_without_touching_user_db(self):
        revenue = self.economy.record_revenue(
            amount=100,
            operation_id="revenue-1",
            actor=str(OWNER_TELEGRAM_ID),
            reason="verified_external_revenue",
            evidence={"event_id": "external-1"},
        )
        self.assertEqual(revenue["status"], "completed")
        self.assertEqual(self.economy.balance("AGENT_TREASURY"), 100)

        result = self.economy.treasury_fund(
            agent_id="agent-1",
            amount=60,
            operation_id="fund-1",
            actor=str(OWNER_TELEGRAM_ID),
            reason="bootstrap",
        )
        self.assertEqual(result["status"], "completed")
        self.assertEqual(self.economy.balance("agent-1"), 60)
        self.assertEqual(self.economy.balance("AGENT_TREASURY"), 40)

    def test_transfer_is_idempotent(self):
        self.economy.record_revenue(
            amount=100, operation_id="revenue-1", actor=str(OWNER_TELEGRAM_ID),
            reason="verified_external_revenue", evidence={"event_id": "external-1"},
        )
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
        self.assertEqual(len(self.economy.ledger()), 5)

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
                self.economy.record_revenue(
                    amount=amount, operation_id=f"rev-{amount}",
                    actor=str(OWNER_TELEGRAM_ID), reason="bad",
                    evidence={"event_id": "bad"},
                )

    def test_operation_ids_are_globally_unique(self):
        self.economy.record_revenue(
            amount=10, operation_id="op-1", actor=str(OWNER_TELEGRAM_ID),
            reason="verified_external_revenue", evidence={"event_id": "external-1"},
        )
        with self.assertRaises(ValueError):
            self.economy.record_revenue(
                amount=10, operation_id="op-1", actor=str(OWNER_TELEGRAM_ID),
                reason="collision", evidence={"event_id": "external-2"},
            )

    def test_proposal_is_read_only(self):
        self.economy.record_revenue(
            amount=20,
            operation_id="revenue-1",
            actor=str(OWNER_TELEGRAM_ID),
            reason="verified_external_revenue",
            evidence={"event_id": "external-1"},
        )
        self.economy.treasury_fund(
            agent_id="agent-1",
            amount=20,
            operation_id="fund-1",
            actor=str(OWNER_TELEGRAM_ID),
            reason="bootstrap",
        )
        ledger_before = list(self.economy.ledger())
        result = self.economy.propose_transfer(
            source_agent="agent-1",
            target_agent="agent-2",
            amount=10,
            operation_id="proposal-1",
            actor=str(OWNER_TELEGRAM_ID),
            reason="work",
        )
        self.assertEqual(result["status"], "proposed")
        self.assertEqual(self.economy.balance("agent-1"), 20)
        self.assertEqual(self.economy.balance("agent-2"), 0)
        self.assertEqual(self.economy.ledger(), ledger_before)

    def test_reward_uses_treasury(self):
        self.economy.record_revenue(
            amount=50,
            operation_id="revenue-1",
            actor=str(OWNER_TELEGRAM_ID),
            reason="verified_external_revenue",
            evidence={"event_id": "external-1"},
        )
        result = self.economy.record_reward(
            agent_id="agent-1",
            amount=20,
            operation_id="reward-1",
            mission_id="m1",
            actor=str(OWNER_TELEGRAM_ID),
        )
        self.assertEqual(result["status"], "completed")
        self.assertEqual(self.economy.balance("agent-1"), 20)
        self.assertEqual(self.economy.balance("AGENT_TREASURY"), 30)

    def test_revenue_requires_evidence(self):
        with self.assertRaises(ValueError):
            self.economy.record_revenue(
                amount=10, operation_id="rev-1", actor=str(OWNER_TELEGRAM_ID),
                reason="missing_evidence", evidence={},
            )

    def test_state_is_persistent_and_separate(self):
        self.economy.record_revenue(
            amount=7.5, operation_id="fund-1", actor=str(OWNER_TELEGRAM_ID),
            reason="verified_external_revenue", evidence={"event_id": "external-1"},
        )
        path = self.root / "state" / "agent_economy.json"
        self.assertTrue(path.exists())
        document = json.loads(path.read_text(encoding="utf-8"))
        self.assertIn("accounts", document)
        self.assertIn("ledger", document)
        self.assertIn("operations", document)
        self.assertNotIn("users", document)
        self.assertNotIn("wallet", document)

    def test_proposal_is_consumed_by_matching_commit(self):
        self.economy.record_revenue(
            amount=30, operation_id="revenue-1", actor=str(OWNER_TELEGRAM_ID),
            reason="verified_external_revenue", evidence={"event_id":"external-1"},
        )
        self.economy.treasury_fund(
            agent_id="agent-1", amount=30, operation_id="fund-1",
            actor=str(OWNER_TELEGRAM_ID), reason="bootstrap",
        )
        proposal = self.economy.propose_transfer(
            source_agent="agent-1", target_agent="agent-2", amount=10,
            operation_id="transfer-1", actor=str(OWNER_TELEGRAM_ID), reason="work",
        )
        self.assertEqual(proposal["status"], "proposed")
        result = self.economy.transfer(
            source_agent="agent-1", target_agent="agent-2", amount=10,
            operation_id="transfer-1", actor=str(OWNER_TELEGRAM_ID), reason="work",
        )
        self.assertEqual(result["status"], "completed")

    def test_proposal_id_cannot_be_reused_for_different_transfer(self):
        self.economy.record_revenue(
            amount=30, operation_id="revenue-1", actor=str(OWNER_TELEGRAM_ID),
            reason="verified_external_revenue", evidence={"event_id":"external-1"},
        )
        self.economy.treasury_fund(
            agent_id="agent-1", amount=30, operation_id="fund-1",
            actor=str(OWNER_TELEGRAM_ID), reason="bootstrap",
        )
        self.economy.propose_transfer(
            source_agent="agent-1", target_agent="agent-2", amount=10,
            operation_id="transfer-1", actor=str(OWNER_TELEGRAM_ID), reason="work",
        )
        with self.assertRaises(ValueError):
            self.economy.transfer(
                source_agent="agent-1", target_agent="agent-2", amount=11,
                operation_id="transfer-1", actor=str(OWNER_TELEGRAM_ID), reason="work",
            )


if __name__ == "__main__":
    unittest.main()