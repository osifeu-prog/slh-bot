import unittest
from unittest.mock import patch

from core.identity import OWNER_TELEGRAM_ID


class MCPIntegrationTests(unittest.TestCase):
    def setUp(self):
        from slh_mcp.auth import Principal
        self.owner = Principal(
            subject=str(OWNER_TELEGRAM_ID),
            role="OWNER",
            permissions=frozenset(),
        )

    def test_railway_projects_returns_identity_only(self):
        from slh_mcp.tools.integrations import railway_projects
        with patch(
            "slh_mcp.tools.integrations.projects",
            return_value=[
                {"id": "project-1", "name": "main", "variables": {"SECRET": "hidden"}}
            ],
        ):
            result = railway_projects(self.owner)
        self.assertEqual(result, [{"id": "project-1", "name": "main"}])

    def test_railway_deployments_is_conservative_when_query_unavailable(self):
        from slh_mcp.tools.integrations import railway_deployments
        with patch(
            "slh_mcp.tools.integrations._safe_project",
            return_value={"id": "project-1", "name": "main"},
        ):
            result = railway_deployments(self.owner, "project-1", "service-1")
        self.assertEqual(result, [])

    def test_github_ci_output_is_redacted_to_status_data(self):
        from slh_mcp.tools.integrations import github_ci_status

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self):
                import json
                return json.dumps({
                    "total_count": 1,
                    "check_runs": [{
                        "name": "validate",
                        "status": "completed",
                        "conclusion": "success",
                        "output": {"text": "secret"},
                        "token": "secret",
                    }],
                }).encode()

        with patch("slh_mcp.tools.integrations.urllib.request.urlopen", return_value=Response()):
            result = github_ci_status(
                self.owner,
                "osifeu-prog/slh-bot",
                "a" * 40,
            )
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["checks"][0], {
            "name": "validate",
            "status": "completed",
            "conclusion": "success",
        })
        self.assertNotIn("token", repr(result).lower())

    def test_invalid_github_commit_is_rejected(self):
        from slh_mcp.tools.integrations import github_ci_status
        with self.assertRaises(ValueError):
            github_ci_status(self.owner, "osifeu-prog/slh-bot", "main")


if __name__ == "__main__":
    unittest.main()
