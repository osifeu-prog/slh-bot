import os
import unittest
from unittest.mock import patch

from core.identity import OWNER_TELEGRAM_ID


class MCPServicePrincipalTests(unittest.TestCase):
    def test_service_principal_is_not_owner(self):
        from core.authority import get_role, has_permission

        with patch.dict(
            os.environ,
            {"SLH_MCP_SERVICE_PRINCIPAL_ID": "slh-mcp"},
            clear=False,
        ):
            self.assertEqual(get_role("slh-mcp"), "MCP_SERVICE")
            self.assertNotEqual(get_role("slh-mcp"), "OWNER")
            self.assertTrue(has_permission("slh-mcp", "agents.manage"))
            self.assertTrue(has_permission("slh-mcp", "exec.audit"))
            self.assertTrue(has_permission("slh-mcp", "economy.mutate_self"))
            self.assertFalse(has_permission("slh-mcp", "some.owner.only.permission"))

    def test_telegram_owner_behavior_is_unchanged(self):
        from core.authority import get_role, has_permission

        self.assertEqual(get_role(str(OWNER_TELEGRAM_ID)), "OWNER")
        self.assertTrue(has_permission(str(OWNER_TELEGRAM_ID), "anything"))


if __name__ == "__main__":
    unittest.main()
