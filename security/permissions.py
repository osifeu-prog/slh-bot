import json
import os

from core.identity import OWNER_TELEGRAM_ID
from core import profile_manager

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROLES_FILE = os.path.join(BASE_DIR, "roles.json")
POLICIES_FILE = os.path.join(BASE_DIR, "policies.json")


def _load_json(path, fallback):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return fallback


def _load_roles():
    return _load_json(ROLES_FILE, {"roles": {}}).get("roles", {})


def _load_policies():
    return _load_json(POLICIES_FILE, {"policies": {}}).get("policies", {})


def _extract_uid(user_or_msg):
    if hasattr(user_or_msg, "from_user") and getattr(user_or_msg.from_user, "id", None):
        return str(user_or_msg.from_user.id)
    if isinstance(user_or_msg, dict):
        return str(user_or_msg.get("id") or user_or_msg.get("uid") or user_or_msg.get("user_id"))
    if hasattr(user_or_msg, "id"):
        return str(user_or_msg.id)
    return str(user_or_msg)


def _is_owner(uid):
    return str(uid) == str(OWNER_TELEGRAM_ID)


def get_role(uid):
    if _is_owner(uid):
        return "owner"
    try:
        user = profile_manager.get_user(uid)
    except Exception:
        return "student"
    return user.get("role", "student")


def get_permissions(uid):
    if _is_owner(uid):
        return ["*"]
    try:
        user = profile_manager.get_user(uid)
    except Exception:
        return []
    return user.get("permissions", [])


def is_admin(user_or_msg):
    uid = _extract_uid(user_or_msg)
    return _is_owner(uid)


def has_permission(user_or_msg, permission):
    uid = _extract_uid(user_or_msg)
    if _is_owner(uid):
        return True

    policies = _load_policies()
    policy = policies.get(permission)
    if policy is None:
        return False

    role = get_role(uid)
    perms = get_permissions(uid)

    if policy == "permission_required":
        return permission in perms

    allowed_roles = policy if isinstance(policy, list) else [str(policy)]
    return role in allowed_roles
