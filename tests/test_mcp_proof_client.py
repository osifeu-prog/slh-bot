import os
import unittest
from unittest.mock import Mock, patch

import requests

from handlers.mcp_proof_handler import read_mcp_proof


class McpProofClientTests(unittest.TestCase):
    def test_missing_bridge_configuration_fails_closed_without_request(self):
        with patch.dict(os.environ, {"SLH_MCP_URL": "", "SLH_MCP_BRIDGE_TOKEN": ""}), patch(
            "handlers.mcp_proof_handler.requests.get"
        ) as get:
            result = read_mcp_proof()

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "UNAVAILABLE")
        self.assertIn("not configured", result["detail"])
        get.assert_not_called()

    def test_returns_runtime_evidence_when_control_plane_proof_passes(self):
        response = Mock(status_code=200)
        response.json.return_value = {
            "status": "PASS",
            "runtime": {
                "state": "running",
                "running": True,
                "boot_ok": True,
                "agent_count": 4,
            },
        }
        with patch.dict(os.environ, {"SLH_MCP_URL": "https://mcp.example.invalid", "SLH_MCP_BRIDGE_TOKEN": "test-only"}), patch(
            "handlers.mcp_proof_handler.requests.get", return_value=response
        ) as get:
            result = read_mcp_proof()

        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "PASS")
        self.assertIn("Telegram", result["detail"])
        self.assertIn("agent_count=4", result["detail"])
        self.assertNotIn("test-only", result["detail"])
        get.assert_called_once_with(
            "https://mcp.example.invalid/internal/telegram/mcp-proof",
            headers={
                "Authorization": "Bearer test-only",
                "Accept": "application/json",
            },
            timeout=15,
        )

    def test_http_403_surfaces_only_safe_auth_diagnostic(self):
        response = Mock(status_code=403)
        response.json.return_value = {
            "diagnostic": {
                "role": "SERVICE",
                "has_agents_view_self": False,
                "permission_count": 1,
            }
        }
        with patch.dict(os.environ, {"SLH_MCP_URL": "https://mcp.example.invalid", "SLH_MCP_BRIDGE_TOKEN": "secret"}), patch(
            "handlers.mcp_proof_handler.requests.get", return_value=response
        ):
            result = read_mcp_proof()

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("HTTP 403", result["detail"])
        self.assertIn("role=SERVICE", result["detail"])
        self.assertIn("agents.view_self=False", result["detail"])
        self.assertIn("permission_count=1", result["detail"])
        self.assertNotIn("secret", result["detail"])

    def test_non_diagnostic_http_error_is_reported_without_token_or_body(self):
        response = Mock(status_code=404)
        response.json.return_value = {"message": "private response body"}
        with patch.dict(os.environ, {"SLH_MCP_URL": "https://mcp.example.invalid", "SLH_MCP_BRIDGE_TOKEN": "secret"}), patch(
            "handlers.mcp_proof_handler.requests.get", return_value=response
        ):
            result = read_mcp_proof()

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("HTTP 404", result["detail"])
        self.assertNotIn("private response body", result["detail"])
        self.assertNotIn("secret", result["detail"])

    def test_network_failure_is_reported_safely(self):
        with patch.dict(os.environ, {"SLH_MCP_URL": "https://mcp.example.invalid", "SLH_MCP_BRIDGE_TOKEN": "secret"}), patch(
            "handlers.mcp_proof_handler.requests.get", side_effect=requests.Timeout()
        ):
            result = read_mcp_proof()

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "ERROR")
        self.assertIn("Timeout", result["detail"])
        self.assertNotIn("secret", result["detail"])


if __name__ == "__main__":
    unittest.main()
