import json
import unittest
from pathlib import Path

from handlers.academy_menu_handler import _button_course_title, _course_category


ROOT = Path(__file__).resolve().parents[1]
MUSIC_COURSES = (
    "music_reading_basics",
    "music_theory_foundations",
    "harmony_voice_leading",
    "voice_and_ear_training",
)


class MusicAcademyContentTests(unittest.TestCase):
    def test_music_courses_are_free_and_all_lessons_exist(self):
        courses = json.loads((ROOT / "courses.json").read_text(encoding="utf-8"))
        for course_id in MUSIC_COURSES:
            with self.subTest(course=course_id):
                course = courses[course_id]
                self.assertEqual(course["access"], "free")
                self.assertEqual([s["id"] for s in course["stages"]], [1, 2, 3, 4, 5])
                for stage in course["stages"]:
                    lesson = ROOT / stage["lesson"]
                    self.assertTrue(lesson.is_file(), str(lesson))
                    text = lesson.read_text(encoding="utf-8")
                    self.assertGreater(len(text), 150)
                    self.assertTrue(stage["name"].strip())

    def test_music_tracks_are_grouped_first_in_academy(self):
        source = (ROOT / "handlers" / "academy_menu_handler.py").read_text(encoding="utf-8")
        self.assertIn('"🎼 מוזיקה, תאוריה וקול"', source)
        self.assertIn('music_first = [', source)
        self.assertIn('בחר מסלול לימוד. ההתקדמות נשמרת', source)

    def test_button_titles_fit_telegram_limits_and_remain_distinct(self):
        courses = json.loads((ROOT / "courses.json").read_text(encoding="utf-8"))
        buttons = []
        for cid in MUSIC_COURSES:
            label = _button_course_title(cid, courses[cid]["title"])
            buttons.append(label)
            self.assertLessEqual(len(f"▶️ {label} · 5/5"), 64)
            self.assertLessEqual(len(f"📖 חזרה · {label}"), 64)
        self.assertEqual(len(set(buttons)), len(buttons))

    def test_voice_course_includes_safety_boundaries(self):
        path = ROOT / "lessons" / "voice_and_ear_training" / "1.txt"
        text = path.read_text(encoding="utf-8")
        self.assertIn("כאב", text)
        self.assertIn("הפסק", text)
        self.assertIn("איש מקצוע", text)


if __name__ == "__main__":
    unittest.main()
