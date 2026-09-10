"""SLH OS — canonical authority and permission gate.

This module is the single source of truth for identity, roles and
authorization decisions. Runtime handlers must not maintain their own
OWNER/ADMIN lists.
"""

from core.identity import OWNER_TELEGRAM_ID
from core.profile_manager import user_exists, get_user

OWNER_ID = str(OWNER_TELEGRAM_ID)
ADMIN_IDS = {OWNER_ID, "5010371391"}
PARTNER_IDS = {"5010371391"}
ALPHA_DISTRIBUTOR_IDS = {OWNER_ID, *PARTNER_IDS}

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
        "exec.safe",
    ],
    "USER": [
        "public.view",
        "agents.view_self",
        "economy.view_self",
        "economy.mutate_self",
        "agents.modify_self",
        "exec.safe",
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

    # The user registry is authoritative for ordinary users.  Check existence
    # before get_user() because get_user() creates a default profile when one
    # is missing; an unknown Telegram identity must never gain USER rights as a
    # side effect of an authorization check.
    if not user_exists(uid):
        return "UNKNOWN"

    profile_role = str(get_user(uid).get("role", "")).strip().lower()

    if profile_role == "student":
        return "USER"

    # Developer/operator identities are intentionally not mapped to USER here.
    # Their operational permissions remain governed by the legacy permission
    # system until that role is explicitly reconciled into this matrix.
    return "UNKNOWN"


def has_permission(uid, permission: str) -> bool:
    uid = normalize_uid(uid)
    if permission == "alpha.distribute":
        return uid in ALPHA_DISTRIBUTOR_IDS

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
