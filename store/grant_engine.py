from core import profile_manager


def apply_grant(uid, grant):
    user = profile_manager.get_user(uid)

    if "permission" in grant:
        perms = user.get("permissions", [])

        if grant["permission"] not in perms:
            perms.append(grant["permission"])

        profile_manager.update_user(uid, {
            "permissions": perms
        })

        return {
            "type": "permission",
            "value": grant["permission"]
        }

    if "course" in grant:
        profile_manager.update_user(uid, {
            "active_course": grant["course"]
        })

        return {
            "type": "course",
            "value": grant["course"]
        }

    return None
