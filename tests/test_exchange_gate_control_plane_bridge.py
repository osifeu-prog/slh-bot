import os
import unittest
from unittest.mock import patch

import webapp


BRIDGE_TOKEN = "test-only-bridge-token"


class ExchangeGateControlPlaneBridgeTests(unittest.TestCase):
    def setUp(self):
        self.client = webapp.app.test_client()

    def test_bridge_requires_bearer_secret(self):
        with patch.dict(os.environ, {"SLH_MCP_BRIDGE_TOKEN": BRIDGE_TOKEN}, clear=False):
            response = self.client.get("/api/internal/exchange-gate")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json(), {"error": "EXCHANGE_CONTROL_AUTH_REQUIRED"})

    def test_status_returns_only_allowlisted_gate_truth(self):
        expected = {
            "variable": "SLH_EXCHANGE_PUBLIC_OPEN",
            "configured": "0",
            "configured_open": False,
            "source": "railway_service_production",
        }
        with patch.dict(os.environ, {"SLH_MCP_BRIDGE_TOKEN": BRIDGE_TOKEN}, clear=False), \
             patch("core.railway_control.exchange_gate_variable_status", return_value=expected):
            response = self.client.get(
                "/api/internal/exchange-gate",
                headers={"Authorization": f"Bearer {BRIDGE_TOKEN}"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"ok": True, **expected})
        self.assertNotIn("BOT_TOKEN", str(response.get_json()))
        self.assertNotIn("RAILWAY_API_TOKEN", str(response.get_json()))

    def test_bridge_is_close_only_and_requires_explicit_action(self):
        close_result = {
            "status": "DEPLOY_TRIGGERED",
            "previous": "1",
            "configured": "0",
            "commit": "a" * 40,
            "deployment_id": "dep-123",
            "service": "slh-cloud-bot",
            "environment": "production",
        }
        headers = {"Authorization": f"Bearer {BRIDGE_TOKEN}"}
        with patch.dict(os.environ, {"SLH_MCP_BRIDGE_TOKEN": BRIDGE_TOKEN}, clear=False), \
             patch("core.railway_control.close_exchange_gate", return_value=close_result) as close:
            opened = self.client.post(
                "/api/internal/exchange-gate",
                json={"action": "open"},
                headers=headers,
            )
            close.assert_not_called()
            self.assertEqual(opened.status_code, 400)
            self.assertEqual(opened.get_json(), {"error": "CLOSE_ONLY_ACTION_REQUIRED"})

            closed = self.client.post(
                "/api/internal/exchange-gate",
                json={"action": "close"},
                headers=headers,
            )
        close.assert_called_once_with()
        self.assertEqual(closed.status_code, 202)
        payload = closed.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["configured"], "0")
        self.assertEqual(payload["deployment_id"], "dep-123")
        self.assertNotIn("token", str(payload).lower())


if __name__ == "__main__":
    unittest.main()
