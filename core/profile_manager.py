from datetime import datetime
import json
import os

import state_manager


DB_PATH = "state/db.json"


def load_db():
    if not os.path.exists(DB_PATH):
        return {
            "users": {},
            "students": {},
            "tasks": {},
            "votes": {}
        }

    with open(DB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_db(db):
    """
    Compatibility writer.

    New mutation code should prefer state_manager.atomic_update().
    """
    os.makedirs("state", exist_ok=True)

    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(
            db,
            f,
            indent=2,
            ensure_ascii=False
        )


def deep_merge(target, source):
    for k, v in source.items():
        if (
            isinstance(v, dict)
            and isinstance(target.get(k), dict)
        ):
            deep_merge(target[k], v)
        else:
            target[k] = v

    return target


def user_exists(uid):
    uid = str(uid)
    db = state_manager.load_db()
    return uid in db.get("users", {})


def _default_user(uid):
    return {
        "name": f"User{uid}",
        "display_name": f"User{uid}",
        "telegram_name": f"User{uid}",
        "role": "student",
        "joined": False,
        "permissions": [],
        "profile": {
            "created": datetime.utcnow().isoformat()
        },
        "wallet": {
            "credits": 0,
            "staked": 0,
            "token_balance": 0
        },
        "academy": {
            "courses": {}
        },
        "gamification": {
            "points": 0,
            "level": 1
        },
        "referral": {
            "code": None,
            "count": 0,
            "commission": 0
        }
    }


def get_user(uid):
    uid = str(uid)

    db = state_manager.load_db()
    users = db.get("users", {})

    if uid in users:
        return users[uid]

    def create_user(db):
        users = db.setdefault("users", {})

        if uid not in users:
            users[uid] = _default_user(uid)

        return users[uid]

    return state_manager.atomic_update(create_user)


def update_user(uid, data):
    uid = str(uid)

    def mutate(db):
        user = (
            db.setdefault("users", {})
              .setdefault(uid, _default_user(uid))
        )

        deep_merge(user, data)
        return user

    return state_manager.atomic_update(mutate)


def get_balance(uid):
    uid = str(uid)
    db = state_manager.load_db()
    user = db.get("users", {}).get(uid)

    if not user:
        return 0

    return user.get("wallet", {}).get("credits", 0)


def add_balance(uid, amount):
    from core.economy_bridge import add_credits, spend_credits

    if amount >= 0:
        return add_credits(
            uid,
            amount,
            reason="profile_manager:add_balance"
        )

    return spend_credits(
        uid,
        -amount,
        reason="profile_manager:add_balance"
    )


def add_points(uid, points, reason="unknown", meta=None):
    uid = str(uid)
    meta = meta or {}
    idempotency_key = meta.get("idempotency_key")

    def mutate(db):
        user = (
            db.setdefault("users", {})
              .setdefault(uid, _default_user(uid))
        )

        points_ledger = user.setdefault("points_ledger", [])

        if idempotency_key:
            for entry in points_ledger:
                if entry.get("meta", {}).get("idempotency_key") == idempotency_key:
                    return dict(user.get("gamification", {}))

        game = user.setdefault("gamification", {})
        before = game.get("points", 0)
        game["points"] = before + points
        game["level"] = (game["points"] // 100) + 1

        points_ledger.append({
            "time": datetime.utcnow().isoformat(),
            "before": before,
            "amount": points,
            "after": game["points"],
            "reason": reason,
            "meta": meta,
        })

        return dict(game)

    return state_manager.atomic_update(mutate)


def complete_course_stage(uid, course, stage):
    uid = str(uid)

    def mutate(db):
        user = (
            db.setdefault("users", {})
              .setdefault(uid, _default_user(uid))
        )

        courses = (
            user.setdefault("academy", {})
                .setdefault("courses", {})
        )

        c = courses.setdefault(
            course,
            {
                "stage": 0,
                "completed": []
            }
        )

        if stage not in c["completed"]:
            c["completed"].append(stage)

        c["stage"] = max(
            c["stage"],
            stage
        )

        return dict(c)

    return state_manager.atomic_update(mutate)


def get_progress(uid):
    db = state_manager.load_db()

    return (
        db.get("users", {})
          .get(str(uid), {})
          .get("academy", {})
          .get("courses", {})
    )
