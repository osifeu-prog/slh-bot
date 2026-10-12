import json
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
COURSE_ID = "governance_game_theory"


def _catalog():
    return json.loads((ROOT / "courses.json").read_text(encoding="utf-8"))


def test_governance_game_theory_is_free_and_has_no_store_dependency():
    courses = _catalog()
    course = courses[COURSE_ID]
    assert course["access"] == "free"
    assert "store_item" not in course
    assert len(course["stages"]) == 8
    assert [stage["id"] for stage in course["stages"]] == list(range(1, 9))


def test_every_governance_lesson_exists_and_has_content():
    course = _catalog()[COURSE_ID]
    for stage in course["stages"]:
        path = ROOT / stage["lesson"]
        assert path.is_file(), f"missing lesson file: {path}"
        assert path.read_text(encoding="utf-8").strip(), f"empty lesson file: {path}"


def test_lesson_engine_loads_first_governance_lesson():
    from core import lesson_engine

    lesson = lesson_engine.get_lesson(COURSE_ID, 1)
    assert lesson is not None
    assert lesson["id"] == 1
    assert lesson["name"] == "מבוא: אמון, כסף ומערכות"
    assert "מטרות" in lesson["content"]


def test_free_governance_course_is_not_locked_for_regular_user():
    from handlers import academy_handler

    with patch("core.authority.is_owner", return_value=False), patch.object(
        academy_handler.academy_manager,
        "get_courses",
        return_value=_catalog(),
    ):
        assert academy_handler._paid_course_lock("test-user", COURSE_ID) is None
