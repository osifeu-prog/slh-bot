"""Authenticated internal Control Plane bridge for standalone MCP."""
from __future__ import annotations

import hmac
import os
from functools import wraps

from flask import Blueprint, jsonify, request

from core.agent_registry import get_agent, list_agents
from core.authority import get_role, get_visible_agents, has_permission
from core.mission_lifecycle import MissionLifecycleService
from core.runtime_service import execute_agent
from core.runtime_service import status as runtime_status

bridge = Blueprint("mcp_bridge", __name__, url_prefix="/api/internal/mcp")


def _authorized() -> bool:
    expected = os.getenv("SLH_MCP_BRIDGE_TOKEN", "").strip()
    supplied = request.headers.get("X-SLH-MCP-Bridge-Token", "").strip()
    return bool(expected and supplied and hmac.compare_digest(supplied, expected))


def _principal():
    return str(request.headers.get("X-SLH-MCP-Principal", "")).strip()


def _require(permission: str):
    if not _authorized():
        return jsonify({"error": "BRIDGE_AUTH_REQUIRED"}), 401
    subject = _principal()
    if not subject or not has_permission(subject, permission):
        return jsonify({"error": "BRIDGE_PERMISSION_DENIED"}), 403
    return None


def _public_agent(agent: dict) -> dict:
    sensitive = {"inbox", "history", "permissions", "owner_id"}
    return {key: value for key, value in agent.items() if key not in sensitive}


def register_mcp_bridge(app):
    app.register_blueprint(bridge)


@bridge.get("/health")
def health():
    if not _authorized():
        return jsonify({"error": "BRIDGE_AUTH_REQUIRED"}), 401
    return jsonify({"status": "ok", "service": "slh-control-plane-bridge"}), 200


@bridge.get("/agents")
def agents():
    denied = _require("agents.view_self")
    if denied:
        return denied
    visible = get_visible_agents(_principal(), list_agents())
    return jsonify({
        "principal": _principal(),
        "role": get_role(_principal()),
        "agents": [_public_agent(item) for item in visible.values()],
    }), 200


@bridge.get("/agents/<agent_id>")
def agent(agent_id):
    denied = _require("agents.view_self")
    if denied:
        return denied
    visible = get_visible_agents(_principal(), list_agents())
    canonical_id, record = get_agent(agent_id)
    if record is None or canonical_id not in visible:
        return jsonify({"error": "AGENT_NOT_VISIBLE"}), 404
    return jsonify({
        "agent": _public_agent(visible[canonical_id]),
    }), 200


@bridge.get("/runtime")
def runtime():
    denied = _require("agents.view_self")
    if denied:
        return denied
    snapshot = runtime_status()
    return jsonify({
        "state": snapshot.get("state"),
        "running": snapshot.get("running"),
        "boot_ok": snapshot.get("boot_ok"),
        "queue_size": snapshot.get("queue_size"),
        "thread_alive": snapshot.get("thread_alive"),
        "agent_count": len(snapshot.get("agents", [])),
    }), 200


@bridge.post("/agents/<agent_id>/execute")
def agent_execute(agent_id):
    denied = _require("agents.modify_self")
    if denied:
        return denied
    payload = request.get_json(silent=True) or {}
    command = str(payload.get("command", "")).strip()
    if not command:
        return jsonify({"error": "COMMAND_REQUIRED"}), 400
    if len(command) > 2000:
        return jsonify({"error": "COMMAND_TOO_LONG"}), 400

    visible = get_visible_agents(_principal(), list_agents())
    canonical_id, record = get_agent(agent_id)
    if record is None or canonical_id not in visible:
        return jsonify({"error": "AGENT_NOT_VISIBLE"}), 404

    try:
        result = execute_agent(canonical_id, command, source="mcp-bridge")
    except Exception:
        return jsonify({"error": "AGENT_RUNTIME_ERROR"}), 500
    return jsonify(result), 200


@bridge.get("/missions")
def missions():
    denied = _require("public.view")
    if denied:
        return denied
    lifecycle = MissionLifecycleService()
    board, _manifest = lifecycle.load_state()
    if not isinstance(board, dict) or board.get("__invalid_state__"):
        return jsonify({"error": "MISSION_BOARD_UNAVAILABLE"}), 503
    allowed = {
        "id", "desc", "status", "assigned_to", "reward",
        "created_at", "assigned_at", "execution_started_at",
        "execution_completed_at", "completed_at",
    }
    rows = [
        {key: mission.get(key) for key in allowed if key in mission}
        for mission in board.get("missions", [])
        if isinstance(mission, dict)
    ]
    return jsonify({"missions": rows}), 200
