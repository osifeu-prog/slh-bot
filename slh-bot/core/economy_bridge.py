from core import profile_manager


def get_balance(uid):
    return profile_manager.get_balance(uid)


def add_credits(uid, amount):
    return profile_manager.add_balance(uid, amount)


def spend_credits(uid, amount):
    current = profile_manager.get_balance(uid)

    if current < amount:
        return False

    return profile_manager.add_balance(uid, -amount)


def reward(uid, credits=0, points=0):
    result = {}

    if credits:
        result["credits"] = profile_manager.add_balance(
            uid,
            credits
        )

    if points:
        result["points"] = profile_manager.add_points(
            uid,
            points
        )

    return result
