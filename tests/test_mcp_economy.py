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

    def test_balance_requires_owned_agent(self):
        from slh_mcp.tools.economy import economy_agent_balance
        source = {"1": {"id":"1","owner_id":"999","name":"other","state":"idle"}}
        with patch("slh_mcp.tools.economy.list_agents", return_value=source),              patch("slh_mcp.tools.economy.get_visible_agents", return_value={}),              patch("slh_mcp.tools.economy.get_agent", return_value=(None, None)):
            with self.assertRaises(PermissionError):
                economy_agent_balance(self.owner, "1")

    def test_proposal_does_not_mutate(self):
        from slh_mcp.tools.economy import economy_propose_transfer
        service = self._service()
        service.record_revenue(
            amount=20, operation_id="rev-1", actor=str(OWNER_TELEGRAM_ID),
            reason="test", evidence={"event_id":"e1"},
        )
        service.treasury_fund(
            agent_id="1", amount=20, operation_id="fund-1",
            actor=str(OWNER_TELEGRAM_ID), reason="test",
        )
        source = {"1": {"id":"1","owner_id":str(OWNER_TELEGRAM_ID),"name":"a","state":"idle"}}
        with patch("slh_mcp.tools.economy._SERVICE", service),              patch("slh_mcp.tools.economy.list_agents", return_value=source),              patch("slh_mcp.tools.economy.get_visible_agents", return_value=source),              patch("slh_mcp.tools.economy.get_agent", return_value=("1", source["1"])):
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
            amount=20, operation_id="rev-1", actor=str(OWNER_TELEGRAM_ID),
            reason="test", evidence={"event_id":"e1"},
        )
        service.treasury_fund(
            agent_id="1", amount=20, operation_id="fund-1",
            actor=str(OWNER_TELEGRAM_ID), reason="test",
        )
        source = {
            "1": {"id":"1","owner_id":str(OWNER_TELEGRAM_ID),"name":"a","state":"idle"},
            "2": {"id":"2","owner_id":str(OWNER_TELEGRAM_ID),"name":"b","state":"idle"},
        }
        with patch("slh_mcp.tools.economy._SERVICE", service),              patch("slh_mcp.tools.economy.list_agents", return_value=source),              patch("slh_mcp.tools.economy.get_visible_agents", return_value=source),              patch("slh_mcp.tools.economy.get_agent", side_effect=[("1",source["1"]),("1",source["1"])]):
            first = economy_commit_transfer(self.owner, "1", "2", 5, "transfer-1", "test")
            second = economy_commit_transfer(self.owner, "1", "2", 5, "transfer-1", "test")
        self.assertEqual(first["status"], "completed")
        self.assertEqual(second["status"], "duplicate")
        self.assertEqual(service.balance("1"), 15)
        self.assertEqual(service.balance("2"), 5)


if __name__ == "__main__":
    unittest.main()
