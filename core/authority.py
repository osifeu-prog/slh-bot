"""SLH OS — canonical authority and permission gate.

This module is the single source of truth for identity, roles and
authorization decisions. Runtime handlers must not maintain their own
OWNER/ADMIN lists.
"""

import os

from core.identity import OWNER_TELEGRAM_ID
from core.profile_manager import user_exists, get_user

OWNER_ID = str(OWNER_TELEGRAM_ID)
ADMIN_IDS = {OWNER_ID, "5010371391"}
PARTNER_IDS = {"5010371391"}


def _csv_ids(name):
    return {
        value.strip()
        for value in os.getenv(name, "").split(",")
        if value.strip().isdigit()
    }


# Developer IDs are configured through Railway/env rather than hard-coded.
# This keeps access revocable without changing the authorization code.
DEVELOPER_IDS = _csv_ids("SLH_DEVELOPER_IDS")
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

    # Precedence is intentional: ADMIN must win over PARTNER so Zvika's
    # existing partner/distributor capability does not mask admin access.
    if uid == OWNER_ID:
        return "OWNER"

    if uid in ADMIN_IDS:
        return "ADMIN"

    if uid in DEVELOPER_IDS:
        return "DEVELOPER"

    if uid in PARTNER_IDS:
        return "PARTNER_READ_ONLY"

    if not user_exists(uid):
        return "UNKNOWN"

    profile_role = str(get_user(uid).get("role", "")).strip().lower()

    if profile_role == "student":
        return "USER"

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

        if owner == uid:
            visible[aid] = agent
        elif agent.get("agent_type") == "system":
            visible[aid] = {
                k: v for k, v in agent.items()
                if k not in ("inbox", "history", "permissions")
            }

    return visible
