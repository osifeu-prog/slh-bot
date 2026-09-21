            response = client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_mcp_route_requires_bearer(self):
        from starlette.testclient import TestClient
        from slh_mcp.server import build_mcp_app

        with TestClient(build_mcp_app()) as client:
            response = client.post("/mcp", headers={"Host": "localhost"})
        self.assertEqual(response.status_code, 401)

    def test_system_snapshot_is_safe(self):
        from unittest.mock import patch
        from slh_mcp.resources import system_snapshot

        with patch("slh_mcp.resources.agents_resource", return_value=[{}, {}]), \
             patch("slh_mcp.tools.missions.missions_list", return_value=[{}]):
            from slh_mcp.auth import Principal
            owner = Principal(str(OWNER_TELEGRAM_ID), "OWNER", frozenset())
            result = system_snapshot(owner)
        self.assertEqual(result["agent_count"], 2)
        self.assertEqual(result["mission_count"], 1)
        self.assertNotIn("token", repr(result).lower())


if __name__ == "__main__":
    unittest.main()