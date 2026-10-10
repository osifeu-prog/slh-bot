import os
import unittest
from unittest.mock import Mock, patch

from core.identity import OWNER_TELEGRAM_ID


class ExchangeGateBridgeClientTests(unittest.TestCase):
    def test_missing_bridge_configuration_fails_closed(self):
        from core.exchange_gate_bridge import (
            ExchangeGateBridgeError,
            exchange_gate_status,
        )

        with patch.dict(
            os.environ,
            {"SLH_MCP_URL": "", "SLH_MCP_BRIDGE_TOKEN": ""},
            clear=False,
        ):
            with self.assertRaises(ExchangeGateBridgeError) as caught:
                exchange_gate_status()
        self.assertEqual(caught.exception.code, "MCP_BRIDGE_NOT_CONFIGURED")

    def test_status_uses_fixed_authenticated_read_route(self):
        from core.exchange_gate_bridge import exchange_gate_status

        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "status": "PASS",
            "configured": "0",
            "configured_open": False,
        }
        with patch.dict(
            os.environ,
            {
                "SLH_MCP_URL": "https://mcp.example",
                "SLH_MCP_BRIDGE_TOKEN": "bridge-test",
            },
            clear=False,
        ), patch(
            "core.exchange_gate_bridge.requests.request",
            return_value=response,
        ) as request:
            result = exchange_gate_status()

        self.assertEqual(result["configured"], "0")
        self.assertEqual(request.call_args.args[0], "GET")
        self.assertEqual(
            request.call_args.args[1],
            "https://mcp.example/internal/telegram/exchange-gate",
        )
        self.assertEqual(
            request.call_args.kwargs["headers"]["Authorization"],
            "Bearer bridge-test",
        )

    def test_close_uses_fixed_post_route_and_requires_deployment_receipt(self):
        from core.exchange_gate_bridge import close_exchange_gate_via_mcp

        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "status": "DEPLOY_TRIGGERED",
            "configured": "0",
            "commit": "a" * 40,
            "deployment_id": "dep-safe-123",
        }
        with patch.dict(
            os.environ,
            {
                "SLH_MCP_URL": "https://mcp.example",
                "SLH_MCP_BRIDGE_TOKEN": "bridge-test",
            },
            clear=False,
        ), patch(
            "core.exchange_gate_bridge.requests.request",
            return_value=response,
        ) as request:
            result = close_exchange_gate_via_mcp()

        self.assertEqual(result["configured"], "0")
        self.assertEqual(request.call_args.args[0], "POST")
        self.assertEqual(
            request.call_args.args[1],
            "https://mcp.example/internal/telegram/exchange-gate/close",
        )

    def test_remote_railway_error_is_returned_as_safe_code_only(self):
        from core.exchange_gate_bridge import (
            ExchangeGateBridgeError,
            exchange_gate_status,
        )

        response = Mock()
        response.status_code = 502
        response.json.return_value = {
            "status": "ERROR",
            "error": "RAILWAY_CONTROL_TOKEN_MISSING",
            "detail": "must never be shown",
        }
        with patch.dict(
            os.environ,
            {
                "SLH_MCP_URL": "https://mcp.example",
                "SLH_MCP_BRIDGE_TOKEN": "bridge-test",
            },
            clear=False,
        ), patch(
            "core.exchange_gate_bridge.requests.request",
            return_value=response,
        ):
            with self.assertRaises(ExchangeGateBridgeError) as caught:
                exchange_gate_status()

        self.assertEqual(caught.exception.code, "RAILWAY_CONTROL_TOKEN_MISSING")
        self.assertNotIn("must never be shown", str(caught.exception))


class ExchangeGateMCPRoutesTests(unittest.TestCase):
    def _client(self, extra_env=None):
        from starlette.testclient import TestClient
        from slh_mcp.server import build_mcp_app

        env = {
            "SLH_MCP_BRIDGE_TOKEN": "bridge-test",
            "SLH_MCP_BRIDGE_PRINCIPAL_ID": str(OWNER_TELEGRAM_ID),
        }
        env.update(extra_env or {})
        return patch.dict(os.environ, env, clear=False), TestClient(build_mcp_app())

    def test_status_route_requires_bridge_auth(self):
        from starlette.testclient import TestClient
        from slh_mcp.server import build_mcp_app

        with patch.dict(
            os.environ,
            {
                "SLH_MCP_BRIDGE_TOKEN": "bridge-test",
                "SLH_MCP_BRIDGE_PRINCIPAL_ID": str(OWNER_TELEGRAM_ID),
            },
            clear=False,
        ), patch("slh_mcp.control_plane_client.self_test", return_value=True):
            with TestClient(build_mcp_app()) as client:
                response = client.get("/internal/telegram/exchange-gate")
        self.assertEqual(response.status_code, 401)

    def test_status_route_forwards_only_gate_value(self):
        from starlette.testclient import TestClient
        from slh_mcp.server import build_mcp_app

        with patch.dict(
            os.environ,
            {
                "SLH_MCP_BRIDGE_TOKEN": "bridge-test",
                "SLH_MCP_BRIDGE_PRINCIPAL_ID": str(OWNER_TELEGRAM_ID),
            },
            clear=False,
        ), patch(
            "slh_mcp.control_plane_client.self_test", return_value=True
        ), patch(
            "slh_mcp.control_plane_client.exchange_gate_status",
            return_value={
                "status": "PASS",
                "configured": "0",
                "configured_open": False,
                "unrelated_secret": "do-not-forward",
            },
        ):
            with TestClient(build_mcp_app()) as client:
                response = client.get(
                    "/internal/telegram/exchange-gate",
                    headers={"Authorization": "Bearer bridge-test"},
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "status": "PASS",
                "configured": "0",
                "configured_open": False,
            },
        )

    def test_close_route_requires_privileged_permission_and_forwards_receipt(self):
        from starlette.testclient import TestClient
        from slh_mcp.server import build_mcp_app

        result = {
            "status": "DEPLOY_TRIGGERED",
            "configured": "0",
            "commit": "a" * 40,
            "deployment_id": "dep-safe-123",
        }
        with patch.dict(
            os.environ,
            {
                "SLH_MCP_BRIDGE_TOKEN": "bridge-test",
                "SLH_MCP_BRIDGE_PRINCIPAL_ID": str(OWNER_TELEGRAM_ID),
            },
            clear=False,
        ), patch(
            "slh_mcp.control_plane_client.self_test", return_value=True
        ), patch(
            "slh_mcp.control_plane_client.exchange_gate_close",
            return_value=result,
        ) as close:
            with TestClient(build_mcp_app()) as client:
                response = client.post(
                    "/internal/telegram/exchange-gate/close",
                    headers={"Authorization": "Bearer bridge-test"},
                    json={"value": "1", "service_id": "attacker-controlled"},
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["configured"], "0")
        self.assertEqual(response.json()["deployment_id"], "dep-safe-123")
        self.assertNotIn("service_id", response.json())
        close.assert_called_once_with()

    def test_close_route_returns_safe_failure_code(self):
        from starlette.testclient import TestClient
        from slh_mcp.server import build_mcp_app

        with patch.dict(
            os.environ,
            {
                "SLH_MCP_BRIDGE_TOKEN": "bridge-test",
                "SLH_MCP_BRIDGE_PRINCIPAL_ID": str(OWNER_TELEGRAM_ID),
            },
            clear=False,
        ), patch(
            "slh_mcp.control_plane_client.self_test", return_value=True
        ), patch(
            "slh_mcp.auth.authorize", return_value=False
        ), patch(
            "slh_mcp.control_plane_client.exchange_gate_close"
        ) as close:
            with TestClient(build_mcp_app()) as client:
                response = client.post(
                    "/internal/telegram/exchange-gate/close",
                    headers={"Authorization": "Bearer bridge-test"},
                )

        self.assertEqual(response.status_code, 403)
        close.assert_not_called()


if __name__ == "__main__":
    unittest.main()
