"""SLH OS — canonical authority and permission gate.

This module is the single source of truth for identity, roles and
authorization decisions. Runtime handlers must not maintain their own
OWNER/ADMIN lists.
"""

from core.identity import OWNER_TELEGRAM_ID

OWNER_ID = str(OWNER_TELEGRAM_ID)
ADMIN_IDS = {OWNER_ID, "5010371391"}

ROLES = {
    "OWNER": ["*"],
    "ADMIN": [
        "agents.view_all",
        "agents.manage",
        "exec.safe",
    ],
    "USER": [
        "agents.view_self",
        "exec.safe",
    ],
}


def normalize_uid(uid):
    if hasattr(uid, "from_user"):
        uid = getattr(uid.from_user, "id", uid)

    if isinstance(uid, dict):
        uid = uid.get("id") or uid.get("uid") or uid.get("user_id")

    if hasattr(uid, "id"):
        uid = uid.id

    return str(uid)


def is_owner(uid) -> bool:
    return normalize_uid(uid) == OWNER_ID


def get_role(uid) -> str:
    uid = normalize_uid(uid)

    if uid == OWNER_ID:
        return "OWNER"

    if uid in ADMIN_IDS:
        return "ADMIN"

    return "USER"


def has_permission(uid, permission: str) -> bool:
    role = get_role(uid)
    permissions = ROLES.get(role, [])

    return "*" in permissions or permission in permissions


def require_owner(uid) -> bool:
    return is_owner(uid)


def require_permission(uid, permission: str) -> bool:
    return has_permission(uid, permission)


def get_visible_agents(uid, agents: dict) -> dict:
    uid = normalize_uid(uid)

    if is_owner(uid):
        return agents

    visible = {}

    for aid, agent in agents.items():
        visibility = agent.get("visibility", "owner_and_self")
        owner = str(agent.get("owner_id", ""))

        if visibility == "owner_only":
            continue

        if owner == uid:
            visible[aid] = agent

        elif agent.get("agent_type") == "system":
            visible[aid] = {
                k: v
                for k, v in agent.items()
                if k not in ("inbox", "history", "permissions")
            }

    return visible
