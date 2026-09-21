"""Canonical agent-capacity policy."""

from __future__ import annotations

import time

from core.profile_manager import get_user
from core.vip_fulfillment import (
    VIP_BASE_AGENT_LIMIT,
    VIP_LAUNCH_AGENT_LIMIT,
    user_has_launch_vip,
)


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
