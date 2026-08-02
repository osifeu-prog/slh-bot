import os

from core import academy_manager
from core import profile_manager


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



def complete_lesson(uid, course_id, stage):

    user = profile_manager.get_user(uid)

    progress = (
        user
        .get("academy", {})
        .get("courses", {})
        .get(course_id, {})
    )

    completed = progress.get(
        "completed",
        []
    )

    # prevent farming rewards
    if stage in completed:
        return {
            "already_completed": True,
            "progress": progress
        }


    result = academy_manager.complete_stage(
        uid,
        course_id,
        stage
    )

    return {
        "already_completed": False,
        "result": result
    }


def can_access_lesson(uid, course_id, stage):

    # שיעור ראשון פתוח לכולם
    if stage <= 1:
        return True

    user = profile_manager.get_user(uid)

    progress = (
        user
        .get("academy", {})
        .get("courses", {})
        .get(course_id, {})
    )

    completed = progress.get(
        "completed",
        []
    )

    # כדי לפתוח שלב חדש צריך להשלים את הקודם
    return (stage - 1) in completed

