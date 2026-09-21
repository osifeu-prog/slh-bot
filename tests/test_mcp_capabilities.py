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

    def test_initial_capabilities_exist(self):
        from slh_mcp.capabilities import list_capabilities

        names = {item.name for item in list_capabilities()}
        for name in (
            "system.health",
            "system.snapshot",
            "agents.list",
            "economy.agent_balance",
            "economy.agent_ledger",
            "economy.propose_transfer",
            "economy.commit_transfer",
            "bots.registry",
            "bots.federation",
            "railway.projects",
            "github.repositories",
        ):
            self.assertIn(name, names)

    def test_shell_is_not_exposed(self):
        from slh_mcp.capabilities import get_capability

        with self.assertRaises(KeyError):
            get_capability("exec.shell")

    def test_read_capabilities_are_not_mutating(self):
        from slh_mcp.capabilities import list_capabilities

        reads = {
            "system.health",
            "system.snapshot",
            "agents.list",
            "agents.get",
            "agents.runtime_status",
            "missions.list",
            "economy.agent_balance",
            "economy.agent_ledger",
            "economy.propose_transfer",
            "railway.projects",
            "railway.services",
            "railway.deployments",
            "github.repositories",
            "github.ci_status",
            "bots.registry",
            "bots.federation",
        }
        for item in list_capabilities():
            if item.name in reads:
                self.assertFalse(item.mutating, item.name)

    def test_bot_registry_contains_no_secret_fields(self):
        from slh_mcp.resources import bot_registry

        with patch(
            "slh_mcp.resources.list_bots",
            return_value=[{
                "alias": "main",
                "username": "@Me_ad_main_bot",
                "label": "main",
                "targets": [{
                    "project": "endearing-amazement",
                    "project_id": "project",
                    "environment": "production",
                    "service": "web",
                    "service_id": "service",
                    "variable": "BOT_TOKEN",
                }],
            }],
        ):
            rows = bot_registry(self.owner)
        self.assertEqual(rows[0]["alias"], "main")
        self.assertNotIn("token", rows[0])
        self.assertNotIn("token", rows[0]["targets"][0])

    def test_agents_resource_uses_live_bridge(self):
        from slh_mcp.resources import agents_resource

        with patch(
            "slh_mcp.tools.agents.control_plane_client.agents",
            return_value={"agents": [{"id": "1", "name": "alpha", "state": "idle"}]},
        ) as bridge:
            result = agents_resource(self.owner)
        bridge.assert_called_once_with(str(OWNER_TELEGRAM_ID))
        self.assertEqual(result[0]["id"], "1")

    def test_tool_audit_contains_capability_only(self):
        from slh_mcp.capabilities import Capability, guarded_handler

        capability = Capability("test.audit", "test", "public.view", False)
        with patch(
            "slh_mcp.capabilities.current_principal",
            return_value=self.owner,
        ), patch(
            "slh_mcp.control_plane_client.authorize",
            return_value=True,
        ) as remote, patch(
            "slh_mcp.capabilities.audit_event",
        ) as audit_event:
            guarded_handler(
                capability,
                lambda secret="hidden": {"ok": True},
            )(secret="hidden")

        remote.assert_called_once_with("public.view", str(OWNER_TELEGRAM_ID))
        audit_event.assert_called_once_with(
            self.owner.subject,
            "mcp:test.audit",
            "mcp",
            "success",
        )

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
        ), patch(
            "slh_mcp.control_plane_client.authorize",
            return_value=False,
        ):
            with self.assertRaises(ToolError):
                handler()
        self.assertEqual(called, [])

    def test_resource_registration_uris_are_unique(self):
        from unittest.mock import MagicMock
        from slh_mcp.resources import register_resources

        uris = []

        def resource(uri, **_kwargs):
            uris.append(uri)
            def decorator(fn):
                return fn
            return decorator

        server = MagicMock()
        server.resource.side_effect = resource
        register_resources(server)
        self.assertEqual(len(uris), len(set(uris)))

    def test_capability_resource_is_machine_readable(self):
        from slh_mcp.resources import capabilities_resource

        rows = capabilities_resource(self.owner)
        names = {row["name"] for row in rows}
        self.assertIn("agents.list", names)
        self.assertIn("economy.commit_transfer", names)
        self.assertTrue(all("permission" in row and "mutating" in row for row in rows))


if __name__ == "__main__":
    unittest.main()