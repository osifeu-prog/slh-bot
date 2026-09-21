import unittest
from unittest.mock import patch


class MCPCanonicalLedgerTests(unittest.TestCase):
    def test_agent_economy_reads_use_economy_permission(self):
        from slh_mcp.capabilities import get_capability

        self.assertEqual(get_capability("economy.agent_balance").permission, "economy.view_self")
        self.assertEqual(get_capability("economy.agent_ledger").permission, "economy.view_self")

    def test_economy_ledger_is_read_only_capability(self):
        from slh_mcp.capabilities import get_capability

        capability = get_capability("economy.ledger")
        self.assertFalse(capability.mutating)
        self.assertEqual(capability.permission, "exec.audit")

    def test_economy_ledger_tool_returns_normalized_events(self):
        from core.identity import OWNER_TELEGRAM_ID
        from slh_mcp.auth import Principal
        from slh_mcp.tools.economic_ledger import economy_ledger

        principal = Principal(
            subject=str(OWNER_TELEGRAM_ID),
            role="OWNER",
            permissions=frozenset(),
        )
        rows = [{
            "domain": "user",
            "timestamp": "t",
            "account_id": "u",
            "counterparty_id": None,
            "amount": 1,
            "currency": "credits",
            "operation_ref": "op",
            "event_type": "ledger",
            "source": "user_ledger",
            "actor": "u",
            "reason": "test",
            "before": 0,
            "after": 1,
            "meta": {},
        }]
        with patch("slh_mcp.tools.economic_ledger.EconomicReadModel.events", return_value=rows):
            result = economy_ledger(principal, limit=10)
        self.assertEqual(result, rows)

    def test_economy_resource_is_read_only(self):
        from slh_mcp.resources import economic_resource
        from core.identity import OWNER_TELEGRAM_ID
        from slh_mcp.auth import Principal

        principal = Principal(
            subject=str(OWNER_TELEGRAM_ID),
            role="OWNER",
            permissions=frozenset(),
        )
        with patch("slh_mcp.resources.current_principal", return_value=principal), \
             patch("slh_mcp.tools.economic_ledger.economic_ledger_summary", return_value={"events": 3}):
            result = economic_resource()
        self.assertEqual(result, {"events": 3})


if __name__ == "__main__":
    unittest.main()

