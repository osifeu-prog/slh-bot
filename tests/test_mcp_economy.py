import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.identity import OWNER_TELEGRAM_ID


class MCPEconomyToolTests(unittest.TestCase):
    def setUp(self):
        from slh_mcp.auth import Principal
        self.owner = Principal(
            subject=str(OWNER_TELEGRAM_ID),
            role="OWNER",
            permissions=frozenset(),
        )
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def _service(self):
        from slh_mcp.agent_economy import AgentEconomyService
        return AgentEconomyService(root=Path(self.tmp.name))

    def _agent_patch(self):
        return patch(
            "slh_mcp.tools.economy.control_plane_client.agent",
            return_value={"agent": {"id": "1", "name": "a"}},
        )

    def test_balance_requires_live_bridge_visibility(self):
        from slh_mcp.tools.economy import economy_agent_balance
        with patch(
            "slh_mcp.tools.economy.control_plane_client.agent",
            return_value={},
        ):
            with self.assertRaises(PermissionError):
                economy_agent_balance(self.owner, "1")

    def test_proposal_does_not_mutate(self):
        from slh_mcp.tools.economy import economy_propose_transfer
        service = self._service()
        service.record_revenue(
            amount=20,
            operation_id="rev-1",
            actor=str(OWNER_TELEGRAM_ID),
            reason="test",
            evidence={"event_id": "e1"},
        )
        service.treasury_fund(
            agent_id="1",
            amount=20,
            operation_id="fund-1",
            actor=str(OWNER_TELEGRAM_ID),
            reason="test",
        )
        with patch("slh_mcp.tools.economy._SERVICE", service), self._agent_patch():
            result = economy_propose_transfer(
                self.owner, "1", "2", 5, "proposal-1", "test"
            )
        self.assertEqual(result["status"], "proposed")
        self.assertEqual(service.balance("1"), 20)
        self.assertEqual(service.ledger()[-1]["entry_type"], "transfer_credit")

    def test_commit_is_idempotent(self):
        from slh_mcp.tools.economy import economy_commit_transfer
        service = self._service()
        service.record_revenue(
            amount=20,
            operation_id="rev-1",
            actor=str(OWNER_TELEGRAM_ID),
            reason="test",
            evidence={"event_id": "e1"},
        )
        service.treasury_fund(
            agent_id="1",
            amount=20,
            operation_id="fund-1",
            actor=str(OWNER_TELEGRAM_ID),
            reason="test",
        )
        with patch("slh_mcp.tools.economy._SERVICE", service), self._agent_patch():
            first = economy_commit_transfer(
                self.owner, "1", "2", 5, "transfer-1", "test"
            )
            second = economy_commit_transfer(
                self.owner, "1", "2", 5, "transfer-1", "test"
            )
        self.assertEqual(first["status"], "completed")
        self.assertEqual(second["status"], "duplicate")
        self.assertEqual(service.balance("1"), 15)
        self.assertEqual(service.balance("2"), 5)


if __name__ == "__main__":
    unittest.main()
