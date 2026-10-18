import os
import unittest
from unittest.mock import patch

from webapp import app


def json_fingerprint(service_id, digest):
    return {
        "ok": True,
        "status": "PASS",
        "source": "state_manager_json",
        "read_only": True,
        "runtime": {
            "railway_project_id": "project-safe",
            "railway_environment_id": "environment-safe",
            "railway_service_id": service_id,
            "run_bot": "0",
        },
        "snapshot": {
            "sha256": digest,
            "schema_sha256": "b" * 64,
            "size_bytes": 1234,
            "mtime_ns": 123456,
            "root_key_count": 5,
            "collections": {
                "users": {"type": "object", "count": 7},
                "ledger": {"type": "array", "count": 12},
                "slh_token_ledger": {"type": "array", "count": 9},
                "exchange_orders": {"type": "object", "count": 0},
                "exchange_trades": {"type": "object", "count": 0},
                "withdrawals": {"type": "list", "count": 0},
            },
        },
    }


class FakeResponse:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


class StateCalibrationRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_local_fingerprint_requires_bearer_token(self):
        with patch.dict(os.environ, {"SLH_MCP_BRIDGE_TOKEN": "test-bridge"}, clear=False):
            response = self.client.get("/internal/ops/state-fingerprint")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["error"], "STATE_CALIBRATION_AUTH_REQUIRED")

    def test_local_fingerprint_returns_only_safe_fingerprint(self):
        sample = json_fingerprint("service-bot", "a" * 64)
        with patch.dict(os.environ, {"SLH_MCP_BRIDGE_TOKEN": "test-bridge"}, clear=False), patch(
            "core.state_fingerprint.build_local_state_fingerprint", return_value=sample
        ):
            response = self.client.get(
                "/internal/ops/state-fingerprint",
                headers={"Authorization": "Bearer test-bridge"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Cache-Control"), "no-store")
        body = response.get_json()
        self.assertEqual(body["snapshot"]["sha256"], "a" * 64)
        self.assertNotIn("balances", response.get_data(as_text=True).lower())
        self.assertNotIn("uid", response.get_data(as_text=True).lower())

    def test_calibration_requires_designated_coordinator_service(self):
        with patch.dict(os.environ, {
            "SLH_MCP_BRIDGE_TOKEN": "test-bridge",
            "RAILWAY_SERVICE_ID": "not-the-web-service",
        }, clear=False):
            response = self.client.get(
                "/internal/ops/state-calibration",
                headers={"Authorization": "Bearer test-bridge"},
            )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["error"], "STATE_CALIBRATION_COORDINATOR_ONLY")

    def test_calibration_collects_three_sanitized_sources(self):
        bot = json_fingerprint("service-bot", "a" * 64)
        postgres = {
            "ok": True,
            "status": "PASS",
            "source": "slh_api_postgres",
            "read_only": True,
            "schema_sha256": "c" * 64,
            "aggregate_sha256": "d" * 64,
            "table_count": 18,
            "total_estimated_rows": 340,
            "financial_tables": [{"table": "token_balances", "estimated_rows": 15}],
        }
        with patch.dict(os.environ, {
            "SLH_MCP_BRIDGE_TOKEN": "test-bridge",
            "SLH_SERVICE_TOKEN": "test-service",
            "RAILWAY_SERVICE_ID": "13d97581-0199-4f6a-80d1-885c9304ffc5",
        }, clear=False), patch(
            "core.state_fingerprint.build_local_state_fingerprint",
            return_value=json_fingerprint("service-web", "e" * 64),
        ), patch(
            "webapp.requests.get",
            side_effect=[FakeResponse(200, bot), FakeResponse(200, postgres)],
        ) as remote_get:
            response = self.client.get(
                "/internal/ops/state-calibration",
                headers={"Authorization": "Bearer test-bridge"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "COLLECTED_REVIEW_REQUIRED")
        self.assertTrue(payload["read_only"])
        self.assertFalse(payload["release_gate"])
        self.assertEqual(payload["sources"]["bot_json"]["snapshot"]["sha256"], "a" * 64)
        self.assertEqual(payload["sources"]["web_json"]["snapshot"]["sha256"], "e" * 64)
        self.assertEqual(payload["sources"]["api_postgres"]["schema_sha256"], "c" * 64)
        self.assertEqual(payload["json_snapshot_comparison"]["same_bytes_at_observation"], False)
        self.assertEqual(remote_get.call_count, 2)
        self.assertEqual(remote_get.call_args_list[0].kwargs["headers"]["Authorization"], "Bearer test-bridge")
        self.assertEqual(remote_get.call_args_list[1].kwargs["headers"]["X-SLH-Service-Token"], "test-service")

    def test_missing_postgres_fingerprint_is_reported_blocked_not_pass(self):
        bot = json_fingerprint("service-bot", "a" * 64)
        with patch.dict(os.environ, {
            "SLH_MCP_BRIDGE_TOKEN": "test-bridge",
            "SLH_SERVICE_TOKEN": "test-service",
            "RAILWAY_SERVICE_ID": "13d97581-0199-4f6a-80d1-885c9304ffc5",
        }, clear=False), patch(
            "core.state_fingerprint.build_local_state_fingerprint",
            return_value=json_fingerprint("service-web", "a" * 64),
        ), patch(
            "webapp.requests.get",
            side_effect=[FakeResponse(200, bot), FakeResponse(404, {"detail": "not public"})],
        ):
            response = self.client.get(
                "/internal/ops/state-calibration",
                headers={"Authorization": "Bearer test-bridge"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "BLOCKED_INCOMPLETE")
        self.assertEqual(payload["sources"]["api_postgres"]["status"], "BLOCKED")
        self.assertEqual(payload["sources"]["api_postgres"]["reason"], "HTTP_404")
        self.assertFalse(payload["release_gate"])


if __name__ == "__main__":
    unittest.main()
