"""Regression tests for the Academy Alpha progression boundary."""

import sys
import types


# Keep the test independent of the production state volume and optional runtime deps.
state = {}


def default_user():
    return {
        "academy": {"courses": {}},
        "gamification": {"points": 0, "level": 1},
    }


def get_user(uid):
    uid = str(uid)
    state.setdefault(uid, default_user())
    return state[uid]


def update_user(uid, data):
    user = get_user(uid)
    academy = user.setdefault("academy", {})
    for key, value in data.get("academy", {}).items():
        if key == "courses":
            academy.setdefault("courses", {}).update(value)
        else:
            academy[key] = value
    return user


def complete_course_stage(uid, course, stage):
    c = get_user(uid)["academy"]["courses"].setdefault(
        course, {"stage": 0, "completed": []}
    )
    if stage in c["completed"]:
        return dict(c)
    current = int(c.get("stage", 0) or 0)
    if current == 0 and stage != 1:
        raise ValueError("sequential_access")
    if current > 0 and stage != current + 1:
        raise ValueError("sequential_access")
    c["completed"].append(stage)
    c["stage"] = stage
    return dict(c)


fake_profile = types.SimpleNamespace(
    get_user=get_user,
    update_user=update_user,
    complete_course_stage=complete_course_stage,
)
fake_reward = types.SimpleNamespace(
    grant=lambda uid, **kwargs: {"credits": 0, "points": 25}
)

# Import production modules after the fake persistence/reward boundaries are ready.
from core import academy_manager, lesson_engine  # noqa: E402

academy_manager.profile_manager = fake_profile
academy_manager.reward_engine = fake_reward
lesson_engine.academy_manager = academy_manager


def test_start_initializes_progress_and_is_idempotent():
    uid = "academy-test"
    assert academy_manager.start_course(uid, "bitcoin_mastery") is True
    assert academy_manager.get_course(uid, "bitcoin_mastery") == {
        "stage": 0,
        "completed": []
    }

    academy_manager.complete_stage(uid, "bitcoin_mastery", 1)
    assert academy_manager.start_course(uid, "bitcoin_mastery") is True
    assert academy_manager.get_course(uid, "bitcoin_mastery")["stage"] == 1
    assert academy_manager.get_course(uid, "bitcoin_mastery")["completed"] == [1]


def test_progress_is_non_empty_after_start():
    uid = "progress-test"
    academy_manager.start_course(uid, "bitcoin_mastery")
    assert academy_manager.progress(uid) == {
        "bitcoin_mastery": {
            "stage": 0,
            "completed": [],
            "active": True,
        }
    }


def test_sequential_completion_is_enforced():
    uid = "sequence-test"
    academy_manager.start_course(uid, "bitcoin_mastery")

    blocked = academy_manager.complete_stage(uid, "bitcoin_mastery", 3)
    assert blocked["ok"] is False
    assert blocked["error"] == "sequential_access"

    first = academy_manager.complete_stage(uid, "bitcoin_mastery", 1)
    assert first["ok"] is True
    assert first["progress"]["stage"] == 1

    blocked_again = academy_manager.complete_stage(uid, "bitcoin_mastery", 3)
    assert blocked_again["ok"] is False
    assert blocked_again["error"] == "sequential_access"

    second = academy_manager.complete_stage(uid, "bitcoin_mastery", 2)
    assert second["ok"] is True
    assert second["progress"]["stage"] == 2


def test_lesson_access_requires_started_course_and_previous_completion():
    uid = "lesson-test"

    assert lesson_engine.can_access_lesson(uid, "bitcoin_mastery", 1) is False

    academy_manager.start_course(uid, "bitcoin_mastery")
    assert lesson_engine.can_access_lesson(uid, "bitcoin_mastery", 1) is True
    assert lesson_engine.can_access_lesson(uid, "bitcoin_mastery", 2) is False

    academy_manager.complete_stage(uid, "bitcoin_mastery", 1)
    assert lesson_engine.can_access_lesson(uid, "bitcoin_mastery", 2) is True
    assert lesson_engine.can_access_lesson(uid, "bitcoin_mastery", 3) is False
