import json
import os

from core import profile_manager
from core import economy_bridge


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
            "academy":{
                "active_course":course_id
            }
        }
    )

    return True



def complete_stage(uid, course_id, stage):

    result = profile_manager.complete_course_stage(
        uid,
        course_id,
        stage
    )


    reward = economy_bridge.reward(
        uid,
        credits=10,
        points=25
    )


    return {
        "progress": result,
        "reward": reward
    }



def progress(uid):

    return profile_manager.get_progress(uid)
