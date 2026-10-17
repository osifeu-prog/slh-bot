import os
import unittest
from unittest.mock import patch

from flask import Flask
from contextlib import nullcontext
import hashlib
import json
import tempfile
from pathlib import Path


class MCPBridgeRouteTests(unittest.TestCase):
    def setUp(self):
        from core.mcp_bridge_routes import register_mcp_bridge_routes

        self.app = Flask(__name__)
        register_mcp_bridge_routes(self.app)
        self.client = self.app.test_client()

        self.env = {
            "SLH_MCP_BRIDGE_TOKEN": os.environ.get("SLH_MCP_BRIDGE_TOKEN"),
            "SLH_MCP_BRIDGE_PRINCIPAL_ID": os.environ.get("SLH_MCP_BRIDGE_PRINCIPAL_ID"),
            "SLH_MCP_PRINCIPAL_ID": os.environ.get("SLH_MCP_PRINCIPAL_ID"),
        }
        os.environ["SLH_MCP_BRIDGE_TOKEN"] = "bridge-test"
        os.environ["SLH_MCP_BRIDGE_PRINCIPAL_ID"] = "owner"

    def tearDown(self):
        for key, value in self.env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_missing_auth_is_rejected(self):
        response = self.client.get("/internal/mcp/v1/agents")
        self.assertEqual(response.status_code, 401)

    def test_client_cannot_override_configured_principal(self):
        source = {
            "1": {"id":"1","name":"A","owner_id":"owner","state":"idle"},
        }
        with patch(
            "core.mcp_bridge_routes.list_agents", return_value=source
        ), patch(
            "core.mcp_bridge_routes.get_visible_agents",
            return_value=source,
        ) as visible, patch(
            "core.mcp_bridge_routes.has_permission", return_value=True
        ):
            response = self.client.get(
                "/internal/mcp/v1/agents",
                headers={
                    "Authorization": "Bearer bridge-test",
                    "X-SLH-MCP-Subject": "attacker",
                },
            )

        self.assertEqual(response.status_code, 200)
        visible.assert_called_once_with("owner", source)

    def test_agents_uses_canonical_visibility(self):
        source = {
            "1": {"id":"1","name":"A","owner_id":"owner","state":"idle","inbox":["secret"]},
            "2": {"id":"2","name":"B","owner_id":"other","state":"idle"},
        }
        with patch(
            "core.mcp_bridge_routes.list_agents", return_value=source
        ), patch(
            "core.mcp_bridge_routes.get_visible_agents",
            return_value={"1": source["1"]},
        ) as visible, patch(
            "core.mcp_bridge_routes.has_permission", return_value=True
        ):
            response = self.client.get(
                "/internal/mcp/v1/agents",
                headers={"Authorization": "Bearer bridge-test"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("inbox", response.get_json()["agents"][0])
        visible.assert_called_once_with("owner", source)

    def test_agent_execute_requires_command(self):
        with patch(
            "core.mcp_bridge_routes.has_permission", return_value=True
        ), patch(
            "core.mcp_bridge_routes.list_agents", return_value={
                "1": {"id":"1","name":"A","owner_id":"owner","state":"idle"}
            }
        ), patch(
            "core.mcp_bridge_routes.get_visible_agents",
            return_value={"1": {"id":"1","name":"A","owner_id":"owner","state":"idle"}},
        ), patch(
            "core.mcp_bridge_routes.get_agent",
            return_value=("1", {"id":"1","name":"A","owner_id":"owner","state":"idle"}),
        ):
            response = self.client.post(
                "/internal/mcp/v1/agents/1/execute",
                json={},
                headers={"Authorization": "Bearer bridge-test"},
            )
        self.assertEqual(response.status_code, 400)


    def test_state_fingerprint_requires_bridge_token(self):
        response = self.client.get("/internal/mcp/v1/state/fingerprint")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json(), {"error": "MCP_BRIDGE_AUTH_REQUIRED"})

    def test_state_fingerprint_requires_view_permission(self):
        with patch("core.mcp_bridge_routes.has_permission", return_value=False):
            response = self.client.get(
                "/internal/mcp/v1/state/fingerprint",
                headers={"Authorization": "Bearer bridge-test"},
            )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json(), {"error": "MCP_BRIDGE_FORBIDDEN"})

    def test_state_fingerprint_reports_hash_and_aggregate_counts_only(self):
        raw = json.dumps({
            "users": {"sensitive-user-id": {"wallet": {"credits": 987654.25}}},
            "ledger": [{"uid": "sensitive-user-id", "amount": -987654.25, "reason": "private-test-marker"}],
            "slh_token_ledger": [],
            "exchange_orders": {"order-secret-id": {"status": "open"}},
        }, separators=(",", ":")).encode("utf-8")
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "db.json"
            db_path.write_bytes(raw)
            with patch("state_manager.DB_FILE", str(db_path)), patch(
                "state_manager._db_lock", return_value=nullcontext()
            ), patch("core.mcp_bridge_routes.has_permission", return_value=True), patch(
                "core.mcp_bridge_routes.os.getenv", side_effect=lambda key, default=None: {
                    "SLH_MCP_BRIDGE_TOKEN": "bridge-test",
                    "SLH_MCP_BRIDGE_PRINCIPAL_ID": "owner",
                    "SLH_MCP_PRINCIPAL_ID": "",
                    "RAILWAY_PROJECT_ID": "project-test",
                    "RAILWAY_ENVIRONMENT_ID": "environment-test",
                    "RAILWAY_SERVICE_ID": "service-test",
                    "RUN_BOT": "0",
                }.get(key, default)
            ):
                response = self.client.get(
                    "/internal/mcp/v1/state/fingerprint",
                    headers={"Authorization": "Bearer bridge-test"},
                )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(payload["size_bytes"], len(raw))
        self.assertEqual(payload["collections"]["users"], {"type": "object", "count": 1})
        self.assertEqual(payload["collections"]["ledger"], {"type": "array", "count": 1})
        self.assertEqual(payload["collections"]["slh_token_ledger"], {"type": "array", "count": 0})
        self.assertEqual(payload["collections"]["exchange_orders"], {"type": "object", "count": 1})
        serialized = response.get_data(as_text=True)
        for secret in ("sensitive-user-id", "987654.25", "private-test-marker", "order-secret-id"):
            self.assertNotIn(secret, serialized)
        self.assertEqual(response.headers.get("Cache-Control"), "no-store")

    def test_state_fingerprint_failure_is_generic_and_read_only(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "db.json"
            db_path.write_text("{ malformed", encoding="utf-8")
            before = db_path.read_bytes()
            with patch("state_manager.DB_FILE", str(db_path)), patch(
                "state_manager._db_lock", return_value=nullcontext()
            ), patch("core.mcp_bridge_routes.has_permission", return_value=True), patch(
                "core.mcp_bridge_routes.os.getenv", side_effect=lambda key, default=None: {
                    "SLH_MCP_BRIDGE_TOKEN": "bridge-test",
                    "SLH_MCP_BRIDGE_PRINCIPAL_ID": "owner",
                    "SLH_MCP_PRINCIPAL_ID": "",
                }.get(key, default)
            ):
                response = self.client.get(
                    "/internal/mcp/v1/state/fingerprint",
                    headers={"Authorization": "Bearer bridge-test"},
                )
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.get_json(), {"error": "STATE_FINGERPRINT_FAILED"})
            self.assertEqual(db_path.read_bytes(), before)

    def test_notification_preferences_route_is_authenticated_and_reads_canonical_state(self):
        denied = self.client.get("/internal/mcp/v1/operator/preferences")
        self.assertEqual(denied.status_code, 401)

        with patch("core.mcp_bridge_routes.has_permission", return_value=True), patch(
            "core.ui_preferences.get_preferences",
            return_value={"theme": "calm", "language": "he", "compact": False, "notification_level": "off"},
        ) as read:
            response = self.client.get(
                "/internal/mcp/v1/operator/preferences",
                headers={"Authorization": "Bearer bridge-test"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["notification_level"], "off")
        self.assertEqual(payload["allowed_levels"], ["off", "milestones", "all"])
        read.assert_called_once_with("owner")

    def test_notification_preferences_route_validates_patch_and_uses_canonical_writer(self):
        headers = {"Authorization": "Bearer bridge-test"}
        with patch("core.mcp_bridge_routes.has_permission", return_value=True), patch(
            "core.ui_preferences.validate_notification_level", return_value="off"
        ), patch(
            "core.ui_preferences.set_preferences",
            return_value={"notification_level": "off"},
        ) as save:
            invalid = self.client.patch(
                "/internal/mcp/v1/operator/preferences",
                json={"notification_level": "off", "extra": True},
                headers=headers,
            )
            response = self.client.patch(
                "/internal/mcp/v1/operator/preferences",
                json={"notification_level": "off"},
                headers=headers,
            )

        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()["direct_command_replies_muted"])
        self.assertFalse(response.get_json()["critical_security_messages_muted"])
        save.assert_called_once_with("owner", notification_level="off")

    def test_notification_preferences_patch_requires_owner_permission(self):
        with patch("core.mcp_bridge_routes.has_permission", return_value=False):
            response = self.client.patch(
                "/internal/mcp/v1/operator/preferences",
                json={"notification_level": "off"},
                headers={"Authorization": "Bearer bridge-test"},
            )
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()