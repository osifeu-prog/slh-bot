import os
import unittest
from unittest.mock import patch

from core import railway_control


class RailwayWorkspaceAuthTests(unittest.TestCase):
    def test_workspace_query_prefers_account_token(self):
        with patch.dict(os.environ, {
            "RAILWAY_API_TOKEN": "account-token-test",
            "RAILWAY_PROJECT_TOKEN": "project-token-test",
            "RAILWAY_API_TOKEN_SLH": "",
            "RAILWAY_PROJECT_TOKEN_SLH": "",
            "RAILWAY_WORKSPACE_ID": "workspace-test",
            "RAILWAY_WORKSPACE_ID_SLH": "",
        }, clear=False), patch.object(
            railway_control, "graphql",
            return_value={"workspace": {"projects": {"edges": [{"node": {"id": "p1", "name": "project"}}]}}},
        ) as graphql:
            result = railway_control.projects()

        self.assertEqual(result, [{"id": "p1", "name": "project"}])
        self.assertTrue(graphql.call_args.kwargs["prefer_account_token"])

    def test_account_token_wins_over_project_token_when_preferred(self):
        with patch.dict(os.environ, {
            "RAILWAY_API_TOKEN": "account-token-test",
            "RAILWAY_PROJECT_TOKEN": "project-token-test",
            "RAILWAY_API_TOKEN_SLH": "",
            "RAILWAY_PROJECT_TOKEN_SLH": "",
        }, clear=False):
            headers = railway_control._auth_headers(prefer_account_token=True)

        self.assertEqual(headers.get("Authorization"), "Bearer account-token-test")
        self.assertNotIn("Project-Access-Token", headers)


if __name__ == "__main__":
    unittest.main()
