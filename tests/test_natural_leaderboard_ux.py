import json
import tempfile
import unittest
from pathlib import Path

from core.ask_router import detect_intent
from core.keyboard_detector import normalize_keyboard_text
from handlers.leaderboard_handler import show_leaderboard


class NaturalLeaderboardUXTests(unittest.TestCase):
    def test_keyboard_layout_is_normalized(self):
        self.assertEqual(
            normalize_keyboard_text("thpv vkuj nuchkho?"),
            "איפה הלוח מובילים?",
        )

    def test_natural_leaderboard_intent(self):
        self.assertEqual(detect_intent("איפה הלוח מובילים?"), "leaderboard")
        self.assertEqual(detect_intent("where is the leaderboard?"), "leaderboard")

    def test_leaderboard_rendering(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "db.json"
            path.write_text(
                json.dumps(
                    {
                        "users": {
                            "1": {"name": "Alice", "gamification": {"points": 50}},
                            "2": {"name": "Bob", "gamification": {"points": 100}},
                        }
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            text = show_leaderboard(str(path))
            self.assertIn("🏆 טבלת המובילים 🏆", text)
            self.assertIn("1. Bob - 100 נקודות", text)
            self.assertIn("2. Alice - 50 נקודות", text)


if __name__ == "__main__":
    unittest.main()
