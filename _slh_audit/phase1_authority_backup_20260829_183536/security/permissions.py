"""Compatibility permission API backed by core.authority."""

from core.authority import (
    is_owner,
    get_role as _authority_get_role,
    has_permission as _authority_has_permission,
    normalize_uid,
)


def _extract_uid(user_or_msg):
    return normalize_uid(user_or_msg)


def _is_owner(uid):
    return is_owner(uid)


def get_role(uid):
    role = _authority_get_role(uid)

    # Preserve legacy lowercase role API used by existing handlers.
    return role.lower() if role else None


def get_permissions(uid):
    from core.authority import ROLES

    role = _authority_get_role(uid)
    return list(ROLES.get(role, []))


def is_admin(user_or_msg):
    return is_owner(user_or_msg)


def has_permission(user_or_msg, permission):
    return _authority_has_permission(user_or_msg, permission)
