import unittest
from unittest.mock import Mock

from core.developer_intent import inspect_investor_overview, normalize_intent


class DeveloperIntentTests(unittest.TestCase):
    def test_investor_intent_is_detected_from_hebrew_request(self):
        self.assertEqual(
            normalize_intent("בדוק את Investor Overview שהגדרנו"),
            "investor_overview",
        )

    def test_runtime_command_intent_is_detected(self):
        self.assertEqual(normalize_intent("בדוק collisions ופקודות"), "runtime_commands")

    def test_unknown_intent_is_rejected(self):
        self.assertIsNone(normalize_intent("deploy production"))

    def test_current_investor_surface_is_reported_as_partial(self):
        result = inspect_investor_overview()
        self.assertEqual(result["intent"], "investor_overview")
        self.assertTrue(result["checks"]["canonical_read_model"])
        self.assertTrue(result["checks"]["telegram_button_or_callback"])
        self.assertTrue(result["checks"]["mini_app_screen"])
        self.assertTrue(result["checks"]["me_api"])
        self.assertEqual(result["status"], "ready")


if __name__ == "__main__":
    unittest.main()
