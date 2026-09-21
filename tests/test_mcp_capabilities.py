import unittest
from unittest.mock import patch

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

        read_names = {
            "system.health",
            "agents.list",
            "agents.get",
            "agents.runtime_status",
            "missions.list",
            "economy.agent_balance",
            "economy.agent_ledger",
            "bots.registry",
        }
        for item in list_capabilities():
            if item.name in read_names:
                self.assertFalse(item.mutating, item.name)

    def test_bot_registry_contains_no_secret_fields(self):
        from slh_mcp.resources import bot_registry

        rows = bot_registry(self.owner)
        self.assertTrue(rows)
        for row in rows:
            keys = {str(k).lower() for k in row}
            self.assertNotIn("token", keys)
            self.assertNotIn("value", keys)
            for target in row.get("targets", []):
                target_keys = {str(k).lower() for k in target}
                self.assertNotIn("token", target_keys)
                self.assertNotIn("value", target_keys)

    def test_agents_resource_is_sanitized(self):
        from slh_mcp.resources import agents_resource

        result = agents_resource(self.owner)
        self.assertIsInstance(result, list)
        for row in result:
            self.assertNotIn("inbox", row)
            self.assertNotIn("history", row)
            self.assertNotIn("permissions", row)
            self.assertNotIn("owner_id", row)

    def test_privileged_capability_requires_canonical_permission(self):
        from mcp.server.mcpserver.exceptions import ToolError
        from slh_mcp.auth import Principal
        from slh_mcp.capabilities import get_capability, guarded_handler

        called = []
        capability = get_capability("bots.registry")
        handler = guarded_handler(capability, lambda: called.append(True))

        with patch(
            "slh_mcp.capabilities.current_principal",
            return_value=Principal("1", "UNKNOWN", frozenset()),
        ):
            with self.assertRaises(ToolError):
                handler()
        self.assertEqual(called, [])


if __name__ == "__main__":
    unittest.main()
