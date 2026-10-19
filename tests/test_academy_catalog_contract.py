"""Static contract checks for the canonical Academy catalog.

These tests are intentionally read-only: they inspect repository files only and
never load or mutate production user progress, entitlements, or balances.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read_json(relative_path):
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))


def test_every_course_has_valid_identity_access_and_stage_sequence():
    courses = _read_json("courses.json")
    assert courses, "canonical course catalog must not be empty"
    assert len(courses) == len(set(courses)), "course IDs must be unique"

    for course_id, course in courses.items():
        assert course_id.strip(), "course ID must not be blank"
        assert (course.get("title") or course.get("name") or "").strip(), (
            f"{course_id}: display title/name is required"
        )
        assert course.get("access", "free") in {"free", "paid"}, (
            f"{course_id}: access must be free or paid"
        )
        stages = course.get("stages")
        assert isinstance(stages, list) and stages, (
            f"{course_id}: at least one stage is required"
        )
        stage_ids = [stage.get("id") for stage in stages]
        assert stage_ids == list(range(1, len(stages) + 1)), (
            f"{course_id}: stage IDs must be contiguous and start at 1"
        )
        for stage in stages:
            lesson = stage.get("lesson")
            assert isinstance(lesson, str) and lesson.strip(), (
                f"{course_id} stage {stage.get('id')}: lesson path is required"
            )
            lesson_path = (ROOT / lesson).resolve()
            assert lesson_path.is_relative_to(ROOT.resolve()), (
                f"{course_id} stage {stage.get('id')}: lesson path escapes repository"
            )
            assert lesson_path.is_file(), (
                f"{course_id} stage {stage.get('id')}: missing lesson file {lesson}"
            )


def test_paid_courses_map_to_a_stars_only_store_grant_for_the_same_course():
    courses = _read_json("courses.json")
    items = _read_json("store/items.json")

    for course_id, course in courses.items():
        if course.get("access", "free") != "paid":
            continue

        item_id = course.get("store_item")
        assert item_id, f"{course_id}: paid course must declare store_item"
        item = items.get(item_id)
        assert item is not None, f"{course_id}: store item {item_id!r} is missing"
        assert item.get("type") == "course", (
            f"{course_id}: {item_id} must be a course product"
        )
        assert item.get("stars_only") is True, (
            f"{course_id}: {item_id} must remain Stars-only"
        )
        assert item.get("grant") == {"course": course_id}, (
            f"{course_id}: {item_id} must grant this exact course and nothing else"
        )
        assert isinstance(item.get("price_stars"), int) and item["price_stars"] > 0, (
            f"{course_id}: {item_id} must have a positive Stars price"
        )


def test_every_course_store_product_points_to_a_known_paid_course():
    courses = _read_json("courses.json")
    items = _read_json("store/items.json")

    for item_id, item in items.items():
        grant = item.get("grant")
        if item.get("type") != "course" and not (
            isinstance(grant, dict) and "course" in grant
        ):
            continue
        assert isinstance(grant, dict) and isinstance(grant.get("course"), str), (
            f"{item_id}: course product must have a course grant"
        )
        course_id = grant["course"]
        assert course_id in courses, (
            f"{item_id}: references unknown course {course_id!r}"
        )
        assert courses[course_id].get("access", "free") == "paid", (
            f"{item_id}: free course {course_id!r} must not be sold as a paid course"
        )
        assert courses[course_id].get("store_item") == item_id, (
            f"{item_id}: catalog/store_item mapping is not reciprocal"
        )
