import json
import os

from core import profile_manager
from core import economy_bridge
from core import reward_engine


COURSE_FILE = "courses.json"


def load_courses():
    if not os.path.exists(COURSE_FILE):
        return {}

    with open(
        COURSE_FILE,
        "r",
        encoding="utf-8"
    ) as f:
        return json.load(f)


def get_courses():
    return load_courses()


def get_course(uid, course_id):
    user = profile_manager.get_user(uid)

    return (
        user
        .get("academy", {})
        .get("courses", {})
        .get(course_id, {})
    )


def start_course(uid, course_id):
    courses = load_courses()

    if course_id not in courses:
        return False

    profile_manager.update_user(
        uid,
        {
            "academy": {
                "active_course": course_id,
                "courses": {
                    course_id: {
                        "stage": 0,
                        "completed": []
                    }
                }
            }
        }
    )

    return True


def complete_stage(uid, course_id, stage):
    courses = load_courses()
    course = courses.get(course_id)
    if not course:
        return {
            "ok": False,
            "error": "course_not_found"
        }

    try:
        stage = int(stage)
    except (TypeError, ValueError):
        return {
            "ok": False,
            "error": "invalid_stage"
        }

    valid_stages = {
        item.get("id")
        for item in course.get("stages", [])
    }
    if stage not in valid_stages:
        return {
            "ok": False,
            "error": "stage_not_found"
        }

    current = get_course(uid, course_id)
    completed = list(current.get("completed", []))
    current_stage = int(current.get("stage", 0) or 0)

    if stage in completed:
        return {
            "ok": True,
            "already_completed": True,
            "progress": current,
            "reward": {
                "credits": 0,
                "points": 0
            }
        }

    if current_stage == 0 and stage != 1:
        return {
            "ok": False,
            "error": "sequential_access"
        }

    if current_stage > 0 and stage != current_stage + 1:
        return {
            "ok": False,
            "error": "sequential_access"
        }

    result = profile_manager.complete_course_stage(
        uid,
        course_id,
        stage
    )

    key = f"{uid}:lesson_complete:{course_id}:{stage}"
    reward = reward_engine.grant(
        uid,
        reason=f"lesson_complete:{course_id}:{stage}",
        credits=0,
        points=25,
        idempotency_key=key
    )

    return {
        "ok": True,
        "already_completed": False,
        "progress": result,
        "reward": reward
    }


def progress(uid):
    user = profile_manager.get_user(uid)
    academy = user.get("academy", {})
    courses = academy.get("courses", {})
    active_course = academy.get("active_course")

    result = {}
    for course_id, course in courses.items():
        result[course_id] = {
            "stage": int(course.get("stage", 0) or 0),
            "completed": list(course.get("completed", [])),
            "active": course_id == active_course
        }

    return result
