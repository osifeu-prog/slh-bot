"""SLH OS — canonical authority and permission gate.

This module is the single source of truth for identity, roles and
authorization decisions. Runtime handlers must not maintain their own
OWNER/ADMIN lists.
"""

import os

from core.identity import OWNER_TELEGRAM_ID
from core.profile_manager import user_exists, get_user

OWNER_ID = str(OWNER_TELEGRAM_ID)
# ADMIN is intentionally reserved for the owner until an explicit future
# admin policy is introduced. Developer access is a separate role.
ADMIN_IDS = {OWNER_ID}
PARTNER_IDS = set()  # 5010371391 suspended pending accounting reconciliation


def _csv_ids(name):
    return {
        value.strip()
        for value in os.getenv(name, "").split(",")
        if value.strip().isdigit()
    }


# Environment IDs remain a safe bootstrap/override mechanism. Normal
# day-to-day developer grants are persisted on the user profile and can be
# managed by the OWNER through handlers/dev_admin.py.
DEVELOPER_IDS = _csv_ids("SLH_DEVELOPER_IDS")
MCP_SERVICE_PRINCIPAL_ID = str(os.getenv("SLH_MCP_SERVICE_PRINCIPAL_ID", "slh-mcp")).strip()
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
        "exec.audit",
    ],
    "DEVELOPER": [
        "agents.view_all",
        "exec.audit",
        "economy.view_self",
        "economy.mutate_self",
        "agents.modify_self",
        "public.view",
    ],
    "MCP_SERVICE": [
        "public.view",
        "agents.view_all",
        "agents.manage",
        "agents.modify_self",
        "exec.audit",
        "economy.view_self",
        "economy.mutate_self",
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

    if MCP_SERVICE_PRINCIPAL_ID and uid == MCP_SERVICE_PRINCIPAL_ID:
        return "MCP_SERVICE"

    # Explicit developer grants take precedence over legacy admin/partner
    # memberships. This lets a person such as Zvika retain alpha distribution
    # through ALPHA_DISTRIBUTOR_IDS while having a single DEVELOPER role.
    if uid in DEVELOPER_IDS:
        return "DEVELOPER"

    if uid in ADMIN_IDS:
        return "ADMIN"

    if not user_exists(uid):
        return "UNKNOWN"

    profile = get_user(uid) or {}
    profile_role = str(profile.get("role", "")).strip().lower()

    if profile_role == "developer":
        return "DEVELOPER"

    if profile_role == "admin":
        return "ADMIN"

    if profile_role == "student":
        return "USER"

    if uid in PARTNER_IDS:
        return "PARTNER_READ_ONLY"

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
                    k: v for k, v in agent.items()
                    if k not in ("inbox", "history", "permissions", "owner_id")
                }
            continue

        if role in ("ADMIN", "DEVELOPER", "MCP_SERVICE"):
            if agent.get("agent_type") == "system" or owner == uid:
                visible[aid] = {
                    k: v for k, v in agent.items()
                    if k not in ("inbox", "history", "permissions", "owner_id")
                }
            continue

        if owner == uid:
            visible[aid] = agent
        elif agent.get("agent_type") == "system":
            visible[aid] = {
                k: v for k, v in agent.items()
                if k not in ("inbox", "history", "permissions")
            }

    return visible