"""SLH OS — canonical authority and permission gate.

This module is the single source of truth for identity, roles and
authorization decisions. Runtime handlers must not maintain their own
OWNER/ADMIN lists.
"""

from core.identity import OWNER_TELEGRAM_ID

OWNER_ID = str(OWNER_TELEGRAM_ID)

# Transitional compatibility set.  Legacy handlers may still reference
# ADMIN_IDS, so Tzvika remains listed here until those consumers are migrated.
# get_role() resolves PARTNER_READ_ONLY first, preventing ADMIN privilege
# inheritance during the migration window.
ADMIN_IDS = {OWNER_ID, "5010371391"}
PARTNER_IDS = {"5010371391"}

ROLES = {
    "OWNER": ["*"],
    "PARTNER_READ_ONLY": [
        "public.view",
        "investor.view",
        "ai.investor",
        "market.view",
        "agents.view_approved",
    ],
    "ADMIN": [
        "agents.view_all",
        "agents.manage",
    ],
    "USER": [
        "public.view",
        "agents.view_self",
        "economy.view_self",
        "economy.mutate_self",
        "agents.modify_self",
    ],
    "UNKNOWN": [
        "public.view",
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

    if uid in PARTNER_IDS:
        return "PARTNER_READ_ONLY"

    if uid in ADMIN_IDS:
        return "ADMIN"

    # Do not silently elevate an unrecognized identity to USER privileges.
    return "UNKNOWN"


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
    role = get_role(uid)

    if role == "OWNER":
        return agents

    visible = {}

    for aid, agent in agents.items():
        visibility = agent.get("visibility", "owner_and_self")
        owner = str(agent.get("owner_id", ""))

        if visibility == "owner_only":
            continue

        if role == "PARTNER_READ_ONLY":
            # Partner visibility is intentionally restricted to system agents;
            # callers that expose partner data should additionally project only
            # approved fields rather than returning raw agent records.
            if agent.get("agent_type") == "system":
                visible[aid] = {
                    k: v
                    for k, v in agent.items()
                    if k not in ("inbox", "history", "permissions", "owner_id")
                }
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
