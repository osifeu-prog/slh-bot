import unittest
from unittest.mock import patch

from core.identity import OWNER_TELEGRAM_ID


class MCPBotFederationTests(unittest.TestCase):
    def setUp(self):
        from slh_mcp.auth import Principal
        self.owner = Principal(
            subject=str(OWNER_TELEGRAM_ID),
            role="OWNER",
            permissions=frozenset(),
        )

    def test_federation_never_returns_token_values(self):
        from slh_mcp.tools.bots import bots_federation

        registry = [{
            "alias": "main",
            "username": "MainBot",
            "label": "Control",
            "targets": [{
                "project": "project",
                "project_id": "p1",
                "service": "web",
                "service_id": "s1",
                "environment": "production",
                "variable": "BOT_TOKEN",
            }],
        }]
        with patch("slh_mcp.tools.bots.list_bots", return_value=registry),              patch("slh_mcp.tools.bots.railway_projects", return_value=[{"id":"p1","name":"project"}]),              patch(
                 "slh_mcp.tools.bots.railway_deployments",
                 return_value=[{
                     "service_id":"s1",
                     "service_name":"web",
                     "id":"d1",
                     "status":"SUCCESS",
                 }],
             ):
            result = bots_federation(self.owner)

        self.assertEqual(result[0]["targets"][0]["state"], "READY")
        self.assertNotIn("token_value", repr(result).lower())
        self.assertNotIn("secret", repr(result).lower())

    def test_missing_project_is_explicit(self):
        from slh_mcp.tools.bots import bots_federation

        registry = [{
            "alias": "air",
            "username": "AIR",
            "label": "AIR",
            "targets": [{
                "project": "missing",
                "project_id": "missing",
                "service": "air",
                "service_id": "s1",
                "environment": "production",
                "variable": "TELEGRAM_TOKEN",
            }],
        }]
        with patch("slh_mcp.tools.bots.list_bots", return_value=registry),              patch("slh_mcp.tools.bots.railway_projects", return_value=[]),              patch("slh_mcp.tools.bots.railway_deployments", return_value=[]):
            result = bots_federation(self.owner)
        self.assertEqual(result[0]["targets"][0]["state"], "PROJECT_MISSING")


if __name__ == "__main__":
    unittest.main()
