import json
from pathlib import Path
from unittest.mock import patch

from core import academy_manager
from core import academy_release
from core import lesson_engine


ROOT = Path(__file__).resolve().parents[1]


def test_ai_history_course_is_free_and_first_lesson_published():
    courses = json.loads((ROOT / "courses.json").read_text(encoding="utf-8"))
    course = courses["ai_history"]

    assert course["access"] == "free"
    assert course["stages"][0]["published"] is True
    assert course["stages"][1]["published"] is False
    assert course["announcement_scope"] == "all_bound_groups"


def test_unpublished_ai_history_lesson_is_locked_until_release():
    with patch.object(
        academy_manager,
        "get_courses",
        return_value={
            "ai_history": {
                "stages": [
                    {"id": 1, "published": True},
                    {"id": 2, "published": False},
                ]
            }
        },
    ), patch.object(
        academy_manager,
        "get_course",
        return_value={"stage": 1, "completed": [1]},
    ):
        assert lesson_engine.can_access_lesson("100", "ai_history", 2) is False


def test_bound_group_filter_includes_all_bound_roles():
    fake_db = {
        "community_groups": {
            "-1": {"chat_id": "-1", "role": "free"},
            "-2": {"chat_id": "-2", "role": "vip"},
            "-3": {"chat_id": "-3", "role": "academy"},
            "-4": {"chat_id": "-4", "role": "other"},
        }
    }
    with patch.object(academy_release.state_manager, "load_db", return_value=fake_db):
        assert academy_release.bound_group_ids() == ["-1", "-2", "-3"]
