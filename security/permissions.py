"""
SLH Security Adapter Layer

Future:
RBAC + ABAC + Policy Engine

Current:
delegates to admin_utils
"""

try:
    from admin_utils import is_admin as _legacy_is_admin
except Exception:
    _legacy_is_admin = None


def is_admin(user):
    """
    Compatibility adapter.
    Keeps current security stable.
    """

    if _legacy_is_admin:
        return _legacy_is_admin(user)

    return False


def has_permission(user, permission):
    """
    Future RBAC/ABAC entry point.
    """

    if is_admin(user):
        return True

    return False
