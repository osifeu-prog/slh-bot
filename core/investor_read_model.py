"""Canonical read-only investor view model.

This module deliberately performs no writes. It composes existing canonical
profile/economy/academy/task state for the Investor Mini App API.
"""

import json
from pathlib import Path

import state_manager


COURSE_FILE = Path("courses.json")
REWARD_LEDGER_FILE = Path("state/rewards_ledger.json")


def _load_courses():
    if not COURSE_FILE.exists():
        return {}
    try:
        with COURSE_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _load_reward_ledger():
    if not REWARD_LEDGER_FILE.exists():
        return []
    try:
        with REWARD_LEDGER_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _alpha_preview(db, user, uid, courses, progress, personal_tasks):
    """Build a read-only Alpha evidence/eligibility preview.

    This function intentionally does not calculate or promise an allocation.
    Allocation remains policy-gated until an authoritative Alpha policy exists.
    """
    referral = user.get("referral", {})
    if not isinstance(referral, dict):
        referral = {}

    referred_by = referral.get("referred_by")
    users = db.get("users", {})
    referral_verified = bool(
        referred_by
        and str(referred_by) != uid
        and isinstance(users, dict)
        and isinstance(users.get(str(referred_by)), dict)
    )

    course_count = len(courses)
    completed_courses = 0
    completed_stages = 0
    for course_id, course_progress in progress.items():
        if not isinstance(course_progress, dict):
            continue
        completed = course_progress.get("completed", [])
        if not isinstance(completed, list):
            completed = []
        completed_stages += len(set(completed))
        try:
            stage = int(course_progress.get("stage", 0) or 0)
        except (TypeError, ValueError):
            stage = 0
        course_definition = courses.get(course_id, {})
        total_stages = (
            len(course_definition.get("stages", []))
            if isinstance(course_definition, dict)
            else 0
        )
        if total_stages and stage >= total_stages:
            completed_courses += 1

    task_completed = sum(1 for task in personal_tasks if task["status"] == "done")
    onboarding_ok = bool(user.get("joined", False))
    identity_ok = bool(uid)

    return {
        "status": "review" if identity_ok and onboarding_ok else "incomplete",
        "identity": {"status": "verified" if identity_ok else "missing"},
        "onboarding": {"status": "complete" if onboarding_ok else "incomplete"},
        "academy": {
            "status": "complete" if course_count and completed_courses >= course_count else "in_progress",
            "completed_courses": completed_courses,
            "courses": course_count,
            "completed_stages": completed_stages,
        },
        "tasks": {
            "status": "active" if personal_tasks else "none",
            "completed": task_completed,
            "total": len(personal_tasks),
        },
        "referral": {
            "status": "verified" if referral_verified else "not_verified",
            "referred_by": str(referred_by) if referral_verified else None,
        },
        "share": {"status": "unverified"},
        "allocation": {
            "status": "policy_missing",
            "amount": 0,
            "asset": "AIR",
        },
    }


def get_investor_snapshot(uid):
    uid = str(uid)
    db = state_manager.load_db()
    user = db.get("users", {}).get(uid)
    if not isinstance(user, dict):
        raise ValueError("USER_NOT_FOUND")

    wallet = user.get("wallet", {})
    if not isinstance(wallet, dict):
        wallet = {}

    academy = user.get("academy", {})
    if not isinstance(academy, dict):
        academy = {}
    progress = academy.get("courses", {})
    if not isinstance(progress, dict):
        progress = {}

    courses = _load_courses()
    enrolled = sorted(str(course_id) for course_id in progress.keys())

    personal_tasks = []
    tasks = db.get("tasks", {})
    if isinstance(tasks, dict):
        for task_id, task in tasks.items():
            if not isinstance(task, dict):
                continue
            if str(task.get("owner_id", "")) != uid:
                continue

            done_by = task.get("done_by", [])
            if not isinstance(done_by, list):
                done_by = []

            personal_tasks.append({
                "id": str(task_id),
                "title": task.get("title", "?"),
                "reward": task.get("reward", 0),
                "status": (
                    "done"
                    if uid in [str(x) for x in done_by]
                    else task.get("status", "open")
                ),
                "agent": task.get("agent", "unassigned"),
            })

    reward_credits = 0
    reward_points = 0
    recent_rewards = []
    for entry in reversed(_load_reward_ledger()):
        if not isinstance(entry, dict) or str(entry.get("user")) != uid:
            continue

        credits = entry.get("credits", 0)
        points = entry.get("points", 0)
        if isinstance(credits, (int, float)):
            reward_credits += credits
        if isinstance(points, (int, float)):
            reward_points += points

        if credits == 0 and points == 0:
            continue
        recent_rewards.append({
            "time": entry.get("timestamp"),
            "credits": credits,
            "points": points,
            "reason": str(entry.get("reason", "unknown")),
        })
        if len(recent_rewards) >= 10:
            break

    gamification = user.get("gamification", {})
    if not isinstance(gamification, dict):
        gamification = {}

    return {
        "identity": {
            "uid": uid,
            "display_name": user.get("display_name") or user.get("name") or f"User{uid}",
            "role": user.get("role", "student"),
        },
        "wallet": {
            "credits": wallet.get("credits", 0),
            "staked": wallet.get("staked", 0),
            "token_balance": wallet.get("token_balance", 0),
            "ton_wallet": user.get("ton_wallet"),
        },
        "academy": {
            "courses": sorted(str(course_id) for course_id in courses.keys()),
            "enrolled": enrolled,
            "progress": progress,
        },
        "tasks": {
            "personal": personal_tasks,
            "open": sum(1 for task in personal_tasks if task["status"] != "done"),
            "completed": sum(1 for task in personal_tasks if task["status"] == "done"),
        },
        "rewards": {
            "credits": reward_credits,
            "points": gamification.get("points", 0),
            "recent": recent_rewards,
        },
        "airdrop": {
            "status": "not_connected",
        },
        "alpha": _alpha_preview(db, user, uid, courses, progress, personal_tasks),
    }
