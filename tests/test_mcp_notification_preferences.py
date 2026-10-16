import os
import unittest
from unittest.mock import patch

from flask import Flask

from core.mcp_bridge_routes import register_mcp_bridge_routes


class MCPNotificationPreferenceRouteTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        register_mcp_bridge_routes(self.app)
        self.client = self.app.test_client()
        self.env = {
            "SLH_MCP_BRIDGE_TOKEN": os.environ.get("SLH_MCP_BRIDGE_TOKEN"),
            "SLH_MCP_BRIDGE_PRINCIPAL_ID": os.environ.get("SLH_MCP_BRIDGE_PRINCIPAL_ID"),
            "SLH_MCP_PRINCIPAL_ID": os.environ.get("SLH_MCP_PRINCIPAL_ID"),
        }
        os.environ["SLH_MCP_BRIDGE_TOKEN"] = "bridge-test"
        os.environ["SLH_MCP_BRIDGE_PRINCIPAL_ID"] = "8789977826"

    def tearDown(self):
        for key, value in self.env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_get_requires_auth_and_reads_only_canonical_preference(self):
        unauthenticated = self.client.get("/internal/mcp/v1/operator/notifications")
        self.assertEqual(unauthenticated.status_code, 401)

        with patch("core.mcp_bridge_routes.has_permission", return_value=True), patch(
            "core.notification_preferences.get_notification_preferences",
            return_value={
                "ok": True,
                "progress_updates_enabled": False,
                "critical_alerts_enabled": True,
                "scope": "proactive_noncritical_progress_only",
            },
        ) as read:
            response = self.client.get(
                "/internal/mcp/v1/operator/notifications",
                headers={"Authorization": "Bearer bridge-test"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()["progress_updates_enabled"])
        self.assertTrue(response.get_json()["critical_alerts_enabled"])
        read.assert_called_once_with("8789977826")

    def test_patch_requires_exact_boolean_payload_and_mutation_permission(self):
        headers = {"Authorization": "Bearer bridge-test"}
        with patch("core.mcp_bridge_routes.has_permission", return_value=True), patch(
            "core.notification_preferences.set_progress_updates",
            return_value={
                "ok": True,
                "progress_updates_enabled": False,
                "critical_alerts_enabled": True,
                "scope": "proactive_noncritical_progress_only",
            },
        ) as set_preference:
            invalid = self.client.patch(
                "/internal/mcp/v1/operator/notifications",
                json={"progress_updates_enabled": "false"},
                headers=headers,
            )
            response = self.client.patch(
                "/internal/mcp/v1/operator/notifications",
                json={"progress_updates_enabled": False},
                headers=headers,
            )

        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(response.status_code, 200)
        set_preference.assert_called_once_with("8789977826", False)

    def test_mutation_is_forbidden_without_owner_capability(self):
        with patch("core.mcp_bridge_routes.has_permission", return_value=False):
            response = self.client.patch(
                "/internal/mcp/v1/operator/notifications",
                json={"progress_updates_enabled": False},
                headers={"Authorization": "Bearer bridge-test"},
            )
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
