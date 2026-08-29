from core.authority import (
    OWNER_ID,
    ADMIN_IDS,
    is_owner,
    get_role,
    has_permission,
)

_ADMIN_IDS = list(ADMIN_IDS)


def is_admin(m):
    return is_owner(m)


def get_owner():
    return int(OWNER_ID)
