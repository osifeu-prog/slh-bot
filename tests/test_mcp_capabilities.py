import unittest

from core.identity import OWNER_TELEGRAM_ID


class MCPCapabilityTests(unittest.TestCase):
    def setUp(self):
        from slh_mcp.auth import Principal
        self.owner = Principal(
            subject=str(OWNER_TELEGRAM_ID),
            role="OWNER",
            permissions=frozenset(),
        )

    def test_initial_read_capabilities_exist(self):
        from slh_mcp.capabilities import list_capabilities

        names = {item.name for item in list_capabilities()}
        self.assertIn("system.health", names)
        self.assertIn("agents.list", names)
        self.assertIn("economy.agent_balance", names)
        self.assertIn("bots.registry", names)

    def test_shell_is_not_exposed(self):
        from slh_mcp.capabilities import get_capability

        with self.assertRaises(KeyError):
            get_capability("exec.shell")

    def test_read_capabilities_are_not_mutating(self):
        from slh_mcp.capabilities import list_capabilities

        for item in list_capabilities():
            if item.name in {
                "system.health",
                "agents.list",
                "agents.get",
                "agents.runtime_status",
                "missions.list",
                "economy.agent_balance",
                "economy.agent_ledger",
                "bots.registry",
            }:
                self.assertFalse(item.mutating, item.name)

    def test_bot_registry_contains_no_token_value(self):
        from slh_mcp.resources import bot_registry

        rows = bot_registry(self.owner)
        self.assertTrue(rows)
        for row in rows:
            self.assertNotIn("token", {str(k).lower() for k in row})
            self.assertNotIn("value", {str(k).lower() for k in row})

    def test_agents_resource_uses_visibility(self):
        from slh_mcp.resources import agents_resource

        result = agents_resource(self.owner)
        self.assertIsInstance(result, list)
        for row in result:
            self.assertNotIn("inbox", row)
            self.assertNotIn("history", row)


if __name__ == "__main__":
    unittest.main()
