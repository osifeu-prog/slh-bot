"""Canonical AI action router.

The router is deliberately small: it maps user/session intents to existing
read-only authorities and marks mutations for the existing authority gate.
It never performs shell execution, financial mutation, credential changes,
or deployment mutation itself.
"""

from dataclasses import dataclass
from typing import Any, Dict

from core.authority import has_permission
from core.project_context import get_project_context


@dataclass(frozen=True)
class Action:
    name: str
    kind: str  # read_only | mutation
    permission: str | None = None


_ACTIONS = {
    "project": Action("project", "read_only"),
    "status": Action("project", "read_only"),
    "health": Action("health", "read_only"),
    "agents": Action("agents", "read_only", "agents.view_self"),
    "services": Action("services", "read_only"),
    "deploy": Action("deploy", "mutation", "exec.audit"),
    "redeploy": Action("redeploy", "mutation", "exec.audit"),
}


def resolve_action(name: str) -> Action | None:
    key = str(name or "").strip().lstrip("/").lower()
    return _ACTIONS.get(key)


def _health(ctx: Dict[str, Any]) -> Dict[str, Any]:
    health = ctx.get("health", {})
    services = health.get("non_green_application_services", [])
    return {
        "action": "health",
        "kind": "read_only",
        "non_green_count": len(services),
        "non_green_services": services,
    }


def dispatch(action_name: str, uid=None, **kwargs) -> Dict[str, Any]:
    action = resolve_action(action_name)
    if action is None:
        return {
            "ok": False,
            "error": "UNKNOWN_ACTION",
            "action": str(action_name or ""),
        }

    if action.permission and not has_permission(uid, action.permission):
        return {
            "ok": False,
            "error": "FORBIDDEN",
            "action": action.name,
            "kind": action.kind,
        }

    if action.kind == "mutation":
        return {
            "ok": False,
            "error": "AUTHORITY_REQUIRED",
            "action": action.name,
            "kind": "mutation",
            "message": (
                "Mutation must be routed through the existing Authority Gate; "
                "the AI action router does not execute it directly."
            ),
        }

    ctx = get_project_context(uid, kwargs.get("project_id", "slh-canonical"))

    if action.name == "health":
        result = _health(ctx)
    elif action.name == "agents":
        result = {
            "action": "agents",
            "kind": "read_only",
            "count": ctx.get("agents", {}).get("count", 0),
            "active": ctx.get("agents", {}).get("active", 0),
        }
    elif action.name == "services":
        result = {
            "action": "services",
            "kind": "read_only",
            "count": len(ctx.get("services", [])),
            "items": ctx.get("services", []),
        }
    else:
        result = {
            "action": "project",
            "kind": "read_only",
            "project_id": ctx.get("project_id"),
            "identity": ctx.get("identity", {}),
            "runtime": ctx.get("runtime", {}),
            "agents": {
                "count": ctx.get("agents", {}).get("count", 0),
                "active": ctx.get("agents", {}).get("active", 0),
            },
            "services_count": len(ctx.get("services", [])),
            "health": ctx.get("health", {}),
            "deployments": ctx.get("deployments", {}),
        }

    return {"ok": True, **result}
