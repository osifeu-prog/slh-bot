"""Per-user agent display numbering without changing canonical IDs."""

from __future__ import annotations

from core.authority import get_visible_agents, normalize_uid


def _sort_key(item):
    aid, agent = item
    created = str(agent.get("created", ""))
    try:
        numeric_id = int(aid)
    except (TypeError, ValueError):
        numeric_id = 10**18
    return (created, numeric_id, str(agent.get("name", "")).lower())


def personal_agents(uid, agents: dict) -> list[tuple[str, dict]]:
    uid = normalize_uid(uid)
    visible = get_visible_agents(uid, agents)
    rows = []
    for aid, agent in visible.items():
        if str(agent.get("owner_id", "")) == uid:
            rows.append((str(aid), agent))
    return sorted(rows, key=_sort_key)


def format_numbered_agents(uid, agents: dict) -> list[dict]:
    rows = []
    for display_id, (aid, agent) in enumerate(personal_agents(uid, agents), start=1):
        row = dict(agent)
        row["id"] = aid
        row["display_id"] = display_id
        rows.append(row)
    return rows


def resolve_display_agent(uid, agents: dict, identifier: str) -> str:
    identifier = str(identifier).strip()
    if not identifier:
        raise KeyError("EMPTY_AGENT_IDENTIFIER")

    rows = format_numbered_agents(uid, agents)
    if identifier.isdigit():
        display_id = int(identifier)
        for row in rows:
            if row["display_id"] == display_id:
                return str(row["id"])

    for aid, agent in personal_agents(uid, agents):
        if str(aid) == identifier or str(agent.get("name", "")).lower() == identifier.lower():
            return str(aid)

    raise KeyError(identifier)
