"""Canonical agent-capacity policy."""

from __future__ import annotations

import time

from core.profile_manager import get_user
from core.vip_fulfillment import VIP_BASE_AGENT_LIMIT, VIP_LAUNCH_AGENT_LIMIT


def user_has_launch_vip(uid: str, now: int | None = None) -> bool:
    now = int(time.time() if now is None else now)
    user = get_user(str(uid)) or {}
    qualified = bool(
        user.get("vip_launch_offer_qualified")
        or user.get("vip_bundle", {}).get("launch_offer_qualified")
    )
    expires = int(user.get("vip_access_until", 0) or 0)
    return qualified and expires > now


def max_agents_for_user(uid: str, now: int | None = None) -> int:
    if user_has_launch_vip(str(uid), now=now):
        return VIP_LAUNCH_AGENT_LIMIT
    return VIP_BASE_AGENT_LIMIT


def can_create_agent(uid: str, owned_count: int, now: int | None = None) -> bool:
    return int(owned_count) < max_agents_for_user(str(uid), now=now)


def current_agent_limit(uid: str) -> dict:
    limit = max_agents_for_user(str(uid))
    return {
        "limit": limit,
        "vip_launch": limit == VIP_LAUNCH_AGENT_LIMIT,
    }
