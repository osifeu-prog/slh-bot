"""SLH OS Authority Gate — minimal production-safe version."""

OWNER_ID = "8789977826"
ADMIN_IDS = ["8789977826"]

ROLES = {
    "OWNER": ["*"],
    "ADMIN": ["agents.view_all", "agents.manage", "exec.safe"],
    "USER": ["agents.view_self", "exec.safe"],
}

def get_role(uid: str) -> str:
    if uid == OWNER_ID:
        return "OWNER"
    if uid in ADMIN_IDS:
        return "ADMIN"
    return "USER"

def has_permission(uid: str, permission: str) -> bool:
    role = get_role(uid)
    perms = ROLES.get(role, [])
    return "*" in perms or permission in perms

def get_visible_agents(uid: str, agents: dict) -> dict:
    """Return agents visible to the given user id."""
    role = get_role(uid)
    if role == "OWNER":
        return agents
    visible = {}
    for aid, agent in agents.items():
        vis = agent.get("visibility", "owner_and_self")
        owner = str(agent.get("owner_id", ""))
        if vis == "owner_only":
            continue
        if owner == uid:
            visible[aid] = agent
        elif agent.get("agent_type") == "system":
            # allow users to see system agents metadata (optional)
            visible[aid] = {
                k: v for k, v in agent.items()
                if k not in ("inbox", "history", "permissions")
            }
    return visible
