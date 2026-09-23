from datetime import datetime, timezone

import state_manager
from core import academy_manager, profile_manager
from core.authority import ROLES, is_owner


PREREQUISITE_COURSE = "bitcoin_mastery"
REQUESTS_KEY = "developer_access_requests"


def _now():
    return datetime.now(timezone.utc).isoformat()


def _developer_permissions():
    return sorted(ROLES.get("DEVELOPER", []))


def prerequisite_status(uid):
    uid = str(uid)
    course = academy_manager.get_courses().get(PREREQUISITE_COURSE)
    if not course:
        return {"ok": False, "reason": "bitcoin_mastery_missing", "completed": 0, "required": 0}

    stage_ids = {
        int(item["id"])
        for item in course.get("stages", [])
        if item.get("id") is not None
    }
    progress = academy_manager.get_course(uid, PREREQUISITE_COURSE) or {}
    completed = {
        int(value)
        for value in (progress.get("completed", []) or [])
        if str(value).isdigit()
    }
    required = len(stage_ids)
    done = len(stage_ids & completed)

    return {
        "ok": bool(stage_ids) and done == required,
        "reason": None if done == required else "bitcoin_mastery_incomplete",
        "completed": done,
        "required": required,
    }


def request_access(uid):
    uid = str(uid)
    if not profile_manager.user_exists(uid):
        return {"ok": False, "reason": "user_not_found"}

    if is_owner(uid):
        return {"ok": False, "reason": "owner_already_has_access"}

    user = profile_manager.get_user(uid) or {}
    if (
        str(user.get("role", "")).lower() == "developer"
        and str(user.get("developer_access_status", "")).lower() == "active"
    ):
        return {"ok": True, "status": "already_active"}

    prereq = prerequisite_status(uid)
    if not prereq["ok"]:
        return {
            "ok": False,
            "reason": prereq["reason"],
            "completed": prereq["completed"],
            "required": prereq["required"],
        }

    def mutate(db):
        requests = db.setdefault(REQUESTS_KEY, {})
        existing = requests.get(uid)
        if existing and existing.get("status") == "pending":
            return {"ok": True, "status": "pending", "request": existing}

        request = {
            "status": "pending",
            "requested_at": _now(),
            "prerequisite": PREREQUISITE_COURSE,
            "completed": prereq["completed"],
            "required": prereq["required"],
        }
        requests[uid] = request
        return {"ok": True, "status": "pending", "request": request}

    return state_manager.atomic_update(mutate)


def approve_access(uid, approver_uid):
    uid = str(uid)
    approver_uid = str(approver_uid)

    if not is_owner(approver_uid):
        return {"ok": False, "reason": "owner_only"}

    if not profile_manager.user_exists(uid):
        return {"ok": False, "reason": "user_not_found"}

    prereq = prerequisite_status(uid)
    if not prereq["ok"]:
        return {
            "ok": False,
            "reason": prereq["reason"],
            "completed": prereq["completed"],
            "required": prereq["required"],
        }

    def mutate(db):
        user = db.get("users", {}).get(uid)
        if not user:
            return {"ok": False, "reason": "user_not_found"}

        requests = db.setdefault(REQUESTS_KEY, {})
        existing = requests.get(uid)
        if not existing or existing.get("status") != "pending":
            return {"ok": False, "reason": "request_not_pending"}

        user["role"] = "developer"
        user["permissions"] = _developer_permissions()
        user["developer_access_status"] = "active"
        existing.update({
            "status": "approved",
            "reviewed_at": _now(),
            "reviewed_by": approver_uid,
        })
        return {"ok": True, "status": "approved", "request": existing}

    return state_manager.atomic_update(mutate)


def deny_access(uid, approver_uid):
    uid = str(uid)
    approver_uid = str(approver_uid)
    if not is_owner(approver_uid):
        return {"ok": False, "reason": "owner_only"}

    def mutate(db):
        requests = db.setdefault(REQUESTS_KEY, {})
        existing = requests.get(uid)
        if not existing or existing.get("status") != "pending":
            return {"ok": False, "reason": "request_not_pending"}

        existing.update({
            "status": "denied",
            "reviewed_at": _now(),
            "reviewed_by": approver_uid,
        })
        return {"ok": True, "status": "denied", "request": existing}

    return state_manager.atomic_update(mutate)


def pending_requests():
    db = state_manager.load_db()
    requests = db.get(REQUESTS_KEY, {}) or {}
    return {
        str(uid): data
        for uid, data in requests.items()
        if isinstance(data, dict) and data.get("status") == "pending"
    }
