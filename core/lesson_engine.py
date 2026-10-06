import os

from core import academy_manager


def get_lesson(course_id, stage):
    courses = academy_manager.get_courses()
    course = courses.get(course_id)

    if not course:
        return None

    for lesson in course.get("stages", []):
        if lesson.get("id") == stage:
            path = lesson.get("lesson")

            if not os.path.exists(path):
                return None

            with open(
                path,
                "r",
                encoding="utf-8"
            ) as f:
                return {
                    "id": stage,
                    "name": lesson.get("name"),
                    "content": f.read()
                }

    return None


def can_access_lesson(uid, course_id, stage):
    try:
        stage = int(stage)
    except (TypeError, ValueError):
        return False

    if stage < 1:
        return False

    course = academy_manager.get_courses().get(course_id) or {}
    stage_data = next(
        (
            item for item in course.get("stages", [])
            if int(item.get("id", -1)) == stage
        ),
        None,
    )
    if not stage_data:
        return False

    # A lesson can only be entered after the course has been started.
    progress = academy_manager.get_course(uid, course_id)
    if not progress:
        return False

    completed = set(progress.get("completed", []))
    current_stage = int(progress.get("stage", 0) or 0)

    # Completed lessons remain readable even if a release is later retired.
    if stage in completed:
        return True

    # Unpublished lessons stay locked until the owner releases them.
    if stage_data.get("published", True) is not True:
        return False

    # First lesson is available only after /course_<id>.
    if stage == 1:
        return current_stage == 0

    return (stage - 1) in completed


def complete_lesson(uid, course_id, stage):
    try:
        stage = int(stage)
    except (TypeError, ValueError):
        return {
            "already_completed": False,
            "ok": False,
            "error": "invalid_stage"
        }

    progress = academy_manager.get_course(uid, course_id)
    completed = set(progress.get("completed", [])) if progress else set()

    if stage in completed:
        return {
            "already_completed": True,
            "ok": True,
            "progress": progress
        }

    if not can_access_lesson(uid, course_id, stage):
        return {
            "already_completed": False,
            "ok": False,
            "error": "sequential_access"
        }

    result = academy_manager.complete_stage(
        uid,
        course_id,
        stage
    )

    return {
        "already_completed": False,
        **result
    }
