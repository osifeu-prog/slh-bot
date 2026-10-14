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


def has_course_access(uid, course_id):
    """Central server-side gate for course content and completion."""
    course = academy_manager.get_courses().get(course_id)
    if not course:
        return False

    if course.get("access") != "paid":
        return True

    # Owner, existing enrollment, and active VIP are the canonical grants.
    try:
        from core.authority import is_owner
        if is_owner(uid):
            return True
    except Exception:
        pass

    try:
        if academy_manager.get_course(str(uid), course_id):
            return True
    except Exception:
        return False

    try:
        import time
        from core import profile_manager
        if profile_manager.user_exists(str(uid)):
            user = profile_manager.get_user(str(uid)) or {}
            return int(user.get("vip_access_until", 0) or 0) > time.time()
    except Exception:
        return False

    return False


def can_access_lesson(uid, course_id, stage):
    try:
        stage = int(stage)
    except (TypeError, ValueError):
        return False

    if stage < 1 or not has_course_access(uid, course_id):
        return False

    # A lesson cannot be entered until the course itself has been started.
    progress = academy_manager.get_course(uid, course_id)
    if not progress:
        return False

    completed = set(progress.get("completed", []))
    current_stage = int(progress.get("stage", 0) or 0)

    if stage in completed:
        return True

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

    if course_id not in academy_manager.get_courses():
        return {
            "already_completed": False,
            "ok": False,
            "error": "course_not_found"
        }

    if not has_course_access(uid, course_id):
        return {
            "already_completed": False,
            "ok": False,
            "error": "course_locked"
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
