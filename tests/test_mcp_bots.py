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

    def test_federation_joins_registry_and_railway(self):
        from slh_mcp.tools.bots import bots_federation

        registry = [
            {
                "alias": "main",
                "username": "@Me_ad_main_bot",
                "label": "main",
                "targets": [
                    {
                        "project": "endearing-amazement",
                        "project_id": "p1",
                        "environment": "production",
                        "service": "web",
                        "service_id": "s1",
                        "variable": "BOT_TOKEN",
                    }
                ],
            }
        ]

        with patch(
            "slh_mcp.tools.bots.list_bots",
            return_value=registry,
        ), patch(
            "slh_mcp.tools.bots.railway_projects",
            return_value=[{"id": "p1", "name": "endearing-amazement"}],
        ), patch(
            "slh_mcp.tools.bots.railway_deployments",
            return_value=[
                {
                    "service_id": "s1",
                    "service_name": "web",
                    "id": "d1",
                    "status": "SUCCESS",
                    "created_at": "2026-09-21T18:00:00Z",
                }
            ],
        ):
            rows = bots_federation(self.owner)

        target = rows[0]["targets"][0]
        self.assertEqual(target["state"], "READY")
        self.assertEqual(target["project_found"], True)
        self.assertNotIn("token", target)


if __name__ == "__main__":
    unittest.main()
