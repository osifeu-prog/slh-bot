import unittest
from handlers.bug_handler import close_bug_record, is_valid_bug_id, render_bug_reports


class BugRegistryTest(unittest.TestCase):
    def test_bug_id_validation(self):
        self.assertTrue(is_valid_bug_id("BUG_20260927_155808_181213"))
        self.assertFalse(is_valid_bug_id("BUG_foo"))
        self.assertFalse(is_valid_bug_id("../state/db.json"))

    def test_render_defaults_to_open(self):
        reports = [
            {"id": "BUG_20260927_155808_181213", "uid": "1", "text": "Mini App broke", "status": "open"},
            {"id": "BUG_20260927_160000_2", "uid": "2", "text": "old", "status": "closed"},
        ]
        rendered = render_bug_reports(reports)
        self.assertIn("BUG_20260927_155808_181213", rendered)
        self.assertNotIn("BUG_20260927_160000_2", rendered)

    def test_close_bug_record(self):
        reports = [{"id": "BUG_20260927_155808_181213", "uid": "1", "text": "Mini App broke", "status": "open"}]
        result = close_bug_record(reports, "BUG_20260927_155808_181213", "999", "fixed")
        self.assertTrue(result["ok"])
        self.assertEqual(reports[0]["status"], "closed")
        self.assertEqual(reports[0]["closed_by"], "999")
        self.assertEqual(reports[0]["resolution"], "fixed")

    def test_close_rejects_invalid_or_missing(self):
        reports = []
        self.assertEqual(close_bug_record(reports, "../db", "999")["reason"], "invalid_id")
        self.assertEqual(
            close_bug_record(reports, "BUG_20260927_155808_181213", "999")["reason"],
            "not_found",
        )

    def test_close_is_idempotent(self):
        reports = [{"id": "BUG_20260927_155808_181213", "status": "closed"}]
        result = close_bug_record(reports, "BUG_20260927_155808_181213", "999")
        self.assertEqual(result["reason"], "already_closed")


if __name__ == "__main__":
    unittest.main()
