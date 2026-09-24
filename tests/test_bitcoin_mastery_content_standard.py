import unittest
from pathlib import Path


ROOT = Path("lessons/bitcoin_mastery")
REQUIRED = [
    "🎯 מטרת השיעור",
    "📍 חיבור ל-SLH",
    "🔢 דוגמה מספרית",
    "✍️ תרגיל מעשי",
    "❓ בוחן",
    "🔊 גרסה קולית",
    "לאחר שסיימת:",
]


class BitcoinMasteryContentStandardTests(unittest.TestCase):
    def test_all_12_lessons_follow_enrichment_format(self):
        for stage in range(1, 13):
            path = ROOT / f"{stage}.txt"
            self.assertTrue(path.exists(), path)
            text = path.read_text(encoding="utf-8")
            for marker in REQUIRED:
                self.assertIn(marker, text, f"{path} missing {marker}")
            self.assertLess(len(text), 3500, f"{path} exceeds Telegram one-message target")


if __name__ == "__main__":
    unittest.main()
