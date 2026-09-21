import unittest
from unittest.mock import patch


class RailwayCanonicalTargetTests(unittest.TestCase):
    def test_canonical_main_target_uses_current_workspace_project_id(self):
        from core.railway_control import canonical_main_target

        rows = [
            {"name": "some-project", "id": "other-id"},
            {"name": "endearing-amazement", "id": "current-project-id"},
        ]
        with patch("core.railway_control.projects", return_value=rows):
            target = canonical_main_target()

        self.assertEqual(target["project_id"], "current-project-id")
        self.assertEqual(target["project"], "endearing-amazement")
        self.assertEqual(target["service"], "web")

    def test_missing_main_project_reports_visible_projects(self):
        from core.railway_control import canonical_main_target, RailwayControlError

        rows = [{"name": "other", "id": "other-id"}]
        with patch("core.railway_control.projects", return_value=rows):
            with self.assertRaises(RailwayControlError) as ctx:
                canonical_main_target()

        self.assertIn("endearing-amazement", str(ctx.exception))
        self.assertIn("other=other-id", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
