import os
import unittest
from unittest.mock import patch

from core.identity import OWNER_TELEGRAM_ID


class ControlPlaneHttpTests(unittest.TestCase):
    def setUp(self):
        self.env = {
            "SLH_CORE_INTERNAL_KEY": os.environ.get("SLH_CORE_INTERNAL_KEY"),
        }

    def tearDown(self):
        for key, value in self.env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_internal_agents_route_requires_key_and_permission(self):
        import webapp

        os.environ["SLH_CORE_INTERNAL_KEY"] = "expected"
        client = webapp.app.test_client()

        with patch("webapp.list_agents_control", return_value=[]):
            denied = client.get(
                "/api/internal/control-plane/agents",
                headers={
                    "X-SLH-Internal-Key": "wrong",
                    "X-SLH-Principal-Id": str(OWNER_TELEGRAM_ID),
                },
            )
            self.assertEqual(denied.status_code, 403)

            allowed = client.get(
                "/api/internal/control-plane/agents",
                headers={
                    "X-SLH-Internal-Key": "expected",
                    "X-SLH-Principal-Id": str(OWNER_TELEGRAM_ID),
                },
            )
            self.assertEqual(allowed.status_code, 200)
            self.assertEqual(allowed.get_json(), {"agents": []})

    def test_internal_economy_routes_do_not_accept_public_user_auth_as_internal_key(self):
        import webapp

        os.environ["SLH_CORE_INTERNAL_KEY"] = "expected"
        client = webapp.app.test_client()

        response = client.get(
            "/api/internal/control-plane/economy/agent-1",
            headers={
                "X-SLH-Internal-Key": "not-expected",
                "X-SLH-Principal-Id": str(OWNER_TELEGRAM_ID),
            },
        )
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
