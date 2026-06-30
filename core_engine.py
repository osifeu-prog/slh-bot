import json, os
from datetime import datetime

USERS = "state/users.json"
PROGRESS = "state/progress.json"
COURSES = "courses.json"


def load(path):
    if os.path.exists(path):
        try:
            return json.load(open(path))
        except:
            return {}
    return {}


def save(path, data):
    os.makedirs("state", exist_ok=True)
    json.dump(data, open(path, "w"), indent=2)


def get_or_create_user(user_id, name):
    users = load(USERS)
    uid = str(user_id)

    if uid not in users:
        users[uid] = {
            "name": name,
            "created": datetime.now().isoformat()
        }
        save(USERS, users)

    return users[uid]


def set_progress(user_id, course, data):
    progress = load(PROGRESS)
    uid = str(user_id)

    if uid not in progress:
        progress[uid] = {}

    progress[uid][course] = data
    save(PROGRESS, progress)


def get_progress(user_id, course=None):
    progress = load(PROGRESS)
    uid = str(user_id)

    if course:
        return progress.get(uid, {}).get(course, {})
    return progress.get(uid, {})


def get_course(course_name):
    courses = load(COURSES)
    return courses.get(course_name, {})


def next_stage(user_id, course_name):
    course = get_course(course_name)
    if not course:
        return None, "COURSE_NOT_FOUND"

    progress = get_progress(user_id, course_name)

    current = progress.get("current_stage", 0)
    stages = course.get("stages", [])

    if current >= len(stages):
        return None, "COURSE_COMPLETED"

    stage_data = stages[current]

    progress["current_stage"] = current + 1
    progress.setdefault("completed", []).append(current)

    set_progress(user_id, course_name, progress)

    return stage_data, "OK"
