import os
import unittest
from unittest.mock import patch

from core.identity import OWNER_TELEGRAM_ID


class MCPRailwayDeployTests(unittest.TestCase):
    def setUp(self):
        from slh_mcp.auth import Principal
        self.owner = Principal(
            subject=str(OWNER_TELEGRAM_ID),
            role="OWNER",
            permissions=frozenset(),
        )
        self._old = os.environ.get("SLH_MCP_DEPLOY_ALLOWLIST")

    def tearDown(self):
        if self._old is None:
            os.environ.pop("SLH_MCP_DEPLOY_ALLOWLIST", None)
        else:
            os.environ["SLH_MCP_DEPLOY_ALLOWLIST"] = self._old

    def test_read_only_principal_cannot_deploy(self):
        from slh_mcp.auth import Principal
        from slh_mcp.tools.railway_control import railway_deploy

        principal = Principal("1", "UNKNOWN", frozenset())
        os.environ["SLH_MCP_DEPLOY_ALLOWLIST"] = "p|s|e"
        with self.assertRaises(PermissionError):
            railway_deploy(principal, "p", "s", "e", "a" * 40)

    def test_unknown_target_is_rejected(self):
        from slh_mcp.tools.railway_control import railway_deploy

        os.environ["SLH_MCP_DEPLOY_ALLOWLIST"] = "p|s|e"
        with self.assertRaises(PermissionError):
            railway_deploy(self.owner, "other", "s", "e", "a" * 40)

    def test_invalid_sha_is_rejected_before_deploy(self):
        from slh_mcp.tools.railway_control import railway_deploy

        os.environ["SLH_MCP_DEPLOY_ALLOWLIST"] = "p|s|e"
        with patch("slh_mcp.tools.railway_control.railway_control.deploy") as deploy:
            with self.assertRaises(ValueError):
                railway_deploy(self.owner, "p", "s", "e", "bad")
        deploy.assert_not_called()

    def test_permission_comes_from_canonical_authority(self):
        from slh_mcp.tools.railway_control import railway_deploy
        os.environ["SLH_MCP_DEPLOY_ALLOWLIST"] = "p|s|e"
        with patch(
            "slh_mcp.tools.railway_control.has_permission",
            return_value=False,
        ):
            with self.assertRaises(PermissionError):
                railway_deploy(self.owner, "p", "s", "e", "a" * 40)

    def test_deploy_returns_verified_status(self):
        from slh_mcp.tools.railway_control import railway_deploy

        os.environ["SLH_MCP_DEPLOY_ALLOWLIST"] = "p|s|e"
        with patch(
            "slh_mcp.tools.railway_control.railway_control.deploy",
            return_value={"id": "dep-1"},
        ), patch(
            "slh_mcp.tools.railway_control.railway_control.deployment_status",
            return_value={"id": "dep-1", "status": "SUCCESS"},
        ):
            result = railway_deploy(self.owner, "p", "s", "e", "a" * 40)
        self.assertEqual(result["deployment"]["status"], "SUCCESS")


if __name__ == "__main__":
    unittest.main()