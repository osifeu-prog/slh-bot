"""Authenticated internal Control Plane bridge routes for SLH MCP."""
from __future__ import annotations

from flask import jsonify, request

from core.agent_registry import get_agent, list_agents
from core.authority import get_visible_agents, has_permission
from core.mcp_bridge_auth import mcp_principal, require_mcp_bridge_token
from core.mission_lifecycle import MissionLifecycleService
from core.runtime_service import execute_agent, status as runtime_status


_SENSITIVE_AGENT_FIELDS = {"inbox", "history", "permissions", "owner_id", "wallet"}
_MAX_COMMAND_LENGTH = 2000


def _auth():
    error, status = require_mcp_bridge_token(request)
    if error is not None:
        code = "MCP_BRIDGE_NOT_CONFIGURED" if status == 503 else "MCP_BRIDGE_FORBIDDEN"
        return None, (jsonify({"error": code}), status)
    principal = mcp_principal(request)
    if principal is None:
        return None, (jsonify({"error": "MCP_PRINCIPAL_REQUIRED"}), 400)
    return principal, None


def _public_agent(agent: dict) -> dict:
    return {
        key: value
        for key, value in agent.items()
        if key not in _SENSITIVE_AGENT_FIELDS
    }


def _visible_agent(principal: str, agent_id: str):
    visible = get_visible_agents(principal, list_agents())
    canonical_id, agent = get_agent(str(agent_id))
    if agent is None or canonical_id not in visible:
        return None, None, visible
    return canonical_id, agent, visible


def register_mcp_bridge(app):
    @app.get("/api/internal/mcp/system")
    def mcp_system():
        principal, denied = _auth()
        if denied:
            return denied
        if not has_permission(principal, "exec.audit"):
            return jsonify({"error": "FORBIDDEN"}), 403
        agents = get_visible_agents(principal, list_agents())
        board, _manifest = MissionLifecycleService().load_state()
        missions = board.get("missions", []) if isinstance(board, dict) else []
        return jsonify(
            {
                "service": "SLH Control Plane",
                "status": "ok",
                "agent_count": len(agents),
                "mission_count": len(missions) if isinstance(missions, list) else 0,
            }
        )

    @app.post("/api/internal/mcp/authorize")
    def mcp_authorize():
        principal, denied = _auth()
        if denied:
            return denied
        payload = request.get_json(silent=True) or {}
        permission = str(payload.get("permission", "")).strip()
        if not permission or len(permission) > 128:
            return jsonify({"error": "INVALID_PERMISSION"}), 400
        return jsonify({
            "authorized": bool(has_permission(principal, permission)),
            "permission": permission,
        }), 200

    @app.get("/api/internal/mcp/runtime-status")
    def mcp_runtime_status():
        principal, denied = _auth()
        if denied:
            return denied
        if not has_permission(principal, "agents.view_self"):
            return jsonify({"error": "FORBIDDEN"}), 403
        snapshot = runtime_status()
        return jsonify({
            "state": snapshot.get("state"),
            "running": snapshot.get("running"),
            "boot_ok": snapshot.get("boot_ok"),
            "queue_size": snapshot.get("queue_size"),
            "thread_alive": snapshot.get("thread_alive"),
            "agent_count": len(snapshot.get("agents", [])),
        }), 200

    @app.get("/api/internal/mcp/agents")
    def mcp_agents():
        principal, denied = _auth()
        if denied:
            return denied
        visible = get_visible_agents(principal, list_agents())
        return jsonify({"agents": [_public_agent(agent) for agent in visible.values()]})

    @app.get("/api/internal/mcp/agents/<agent_id>")
    def mcp_agent(agent_id):
        principal, denied = _auth()
        if denied:
            return denied
        canonical_id, agent, _visible = _visible_agent(principal, agent_id)
        if agent is None:
            return jsonify({"error": "AGENT_NOT_VISIBLE"}), 404
        return jsonify({"agent": _public_agent({"id": canonical_id, **agent})})

    @app.post("/api/internal/mcp/agents/<agent_id>/execute")
    def mcp_agent_execute(agent_id):
        principal, denied = _auth()
        if denied:
            return denied
        if not has_permission(principal, "agents.modify_self"):
            return jsonify({"error": "FORBIDDEN"}), 403

        canonical_id, agent, _visible = _visible_agent(principal, agent_id)
        if agent is None:
            return jsonify({"error": "AGENT_NOT_VISIBLE"}), 404

        payload = request.get_json(silent=True) or {}
        command = str(payload.get("command", "")).strip()
        if not command:
            return jsonify({"error": "MISSING_COMMAND"}), 400
        if len(command) > _MAX_COMMAND_LENGTH:
            return jsonify({"error": "COMMAND_TOO_LONG"}), 400

        result = execute_agent(canonical_id, command, source="mcp")
        if not isinstance(result, dict):
            return jsonify({"status": "completed", "type": "agent"}), 200
        safe = {
            "status": result.get("status"),
        }
        if result.get("type") is not None:
            safe["type"] = result.get("type")
        if result.get("data") is not None and isinstance(result.get("data"), dict):
            data = result["data"]
            safe["data"] = {
                key: data.get(key)
                for key in ("agent_id", "command", "execution_status", "verified", "mission_id")
                if key in data
            }
        return jsonify(safe), 200

    @app.get("/api/internal/mcp/missions")
    def mcp_missions():
        principal, denied = _auth()
        if denied:
            return denied
        board, _manifest = MissionLifecycleService().load_state()
        if not isinstance(board, dict) or board.get("__invalid_state__"):
            return jsonify({"error": "MISSION_BOARD_UNAVAILABLE"}), 503

        fields = {
            "id", "desc", "status", "assigned_to", "reward", "created_at",
            "assigned_at", "execution_started_at", "execution_completed_at", "completed_at",
        }
        missions = [
            {key: mission.get(key) for key in fields if key in mission}
            for mission in board.get("missions", [])
            if isinstance(mission, dict)
        ]
        return jsonify({"missions": missions})

    @app.get("/api/internal/mcp/missions/<mission_id>")
    def mcp_mission(mission_id):
        principal, denied = _auth()
        if denied:
            return denied
        lifecycle = MissionLifecycleService()
        board, _manifest = lifecycle.load_state()
        mission = lifecycle.find_mission(board, mission_id)
        if mission is None:
            return jsonify({"error": "MISSION_NOT_FOUND"}), 404
        fields = {
            "id", "desc", "status", "assigned_to", "reward", "created_at",
            "assigned_at", "execution_started_at", "execution_completed_at", "completed_at",
        }
        return jsonify({"mission": {key: mission.get(key) for key in fields if key in mission}})

    @app.post("/api/internal/mcp/missions/<mission_id>/complete")
    def mcp_mission_complete(mission_id):
        principal, denied = _auth()
        if denied:
            return denied
        if not has_permission(principal, "agents.manage"):
            return jsonify({"error": "FORBIDDEN"}), 403

        lifecycle = MissionLifecycleService()
        board, manifest = lifecycle.load_state()
        mission = lifecycle.find_mission(board, mission_id)
        if mission is None:
            return jsonify({"error": "MISSION_NOT_FOUND"}), 404

        agent_id = str(mission.get("assigned_to") or "").strip()
        if not agent_id:
            return jsonify({"error": "MISSION_AGENT_REQUIRED"}), 409

        visible = get_visible_agents(principal, list_agents())
        canonical_id, agent = get_agent(agent_id)
        if agent is None or canonical_id not in visible:
            return jsonify({"error": "AGENT_NOT_VISIBLE"}), 403

        result = lifecycle.complete_mission(str(mission_id))
        return jsonify(result), 200

    return app