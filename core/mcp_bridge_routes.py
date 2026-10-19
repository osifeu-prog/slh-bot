"""Authenticated internal Control Plane bridge for the standalone SLH MCP service."""

from __future__ import annotations

import hmac
import os

from flask import jsonify, request

from core.agent_registry import get_agent, list_agents
from core.authority import get_visible_agents, has_permission
from core.runtime_service import execute_agent, status as runtime_status
from core.mission_lifecycle import MissionLifecycleService


_SENSITIVE_AGENT_FIELDS = {"inbox", "history", "permissions", "owner_id"}
_PUBLIC_MISSION_FIELDS = {
    "id", "desc", "status", "assigned_to", "reward", "created_at",
    "assigned_at", "execution_started_at", "execution_completed_at", "completed_at",
}
_MAX_COMMAND_LENGTH = 2000
_STATE_FINGERPRINT_COLLECTIONS = (
    "users",
    "ledger",
    "slh_token_ledger",
    "transactions",
    "exchange_orders",
    "exchange_trades",
    "purchases",
    "processed_transfers",
    "used_ton_txs",
    "used_bnb_txs",
    "ton_deposit_intents",
    "bnb_deposits",
    "slh_deposit_intents",
    "withdrawals",
    "withdrawal_requests",
    "staking_requests",
    "stake_positions",
    "secondary_distribution_pending",
)


def _local_state_fingerprint():
    """Return non-PII evidence about the exact local JSON state used by this process."""
    import hashlib
    import json
    from pathlib import Path

    import state_manager

    configured_path = Path(state_manager.DB_FILE).expanduser()
    path = configured_path if configured_path.is_absolute() else Path.cwd() / configured_path
    path = path.resolve()

    # Use the same inter-process lock as state_manager writers. Hash only the
    # bytes read under that lock; never return file contents or user-specific rows.
    with state_manager._db_lock():
        before = path.stat()
        if before.st_size > 128 * 1024 * 1024:
            raise ValueError("STATE_FILE_TOO_LARGE")
        raw = path.read_bytes()
        after = path.stat()

    before_identity = (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    )
    after_identity = (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    )
    if before_identity != after_identity:
        raise ValueError("STATE_FILE_CHANGED_DURING_READ")

    database = json.loads(raw.decode("utf-8"))
    if not isinstance(database, dict):
        raise ValueError("STATE_ROOT_NOT_OBJECT")

    collections = {}
    for key in _STATE_FINGERPRINT_COLLECTIONS:
        value = database.get(key)
        if key not in database:
            collection_type = "missing"
            count = None
        elif isinstance(value, dict):
            collection_type = "object"
            count = len(value)
        elif isinstance(value, list):
            collection_type = "array"
            count = len(value)
        else:
            collection_type = type(value).__name__
            count = None
        collections[key] = {"type": collection_type, "count": count}

    return {
        "fingerprint_version": 1,
        "source": "local_state_manager_json",
        "db_file_configured": (
            configured_path.as_posix()
            if not configured_path.is_absolute()
            else "<absolute-path-configured>"
        ),
        "db_file_path_kind": "absolute" if configured_path.is_absolute() else "relative",
        "file_exists": True,
        "size_bytes": len(raw),
        "mtime_ns": after.st_mtime_ns,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "root_keys": sorted(str(key) for key in database),
        "collections": collections,
        "runtime": {
            "railway_project_id": os.getenv("RAILWAY_PROJECT_ID") or None,
            "railway_environment_id": os.getenv("RAILWAY_ENVIRONMENT_ID") or None,
            "railway_service_id": os.getenv("RAILWAY_SERVICE_ID") or None,
            "run_bot": os.getenv("RUN_BOT", "unset"),
        },
    }



def _principal():
    expected = os.getenv("SLH_MCP_BRIDGE_TOKEN", "").strip()
    if not expected:
        return None, (jsonify({"error": "MCP_BRIDGE_NOT_CONFIGURED"}), 503)
    authorization = request.headers.get("Authorization", "").strip()
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token or not hmac.compare_digest(token, expected):
        return None, (jsonify({"error": "MCP_BRIDGE_AUTH_REQUIRED"}), 401)

    subject = (
        os.getenv("SLH_MCP_BRIDGE_PRINCIPAL_ID", "").strip()
        or os.getenv("SLH_MCP_PRINCIPAL_ID", "").strip()
    )
    if not subject:
        return None, (jsonify({"error": "MCP_BRIDGE_PRINCIPAL_NOT_CONFIGURED"}), 503)
    return subject, None


def _require(permission: str):
    subject, error = _principal()
    if error:
        return None, error
    if not has_permission(subject, permission):
        return None, (jsonify({"error": "MCP_BRIDGE_FORBIDDEN"}), 403)
    return subject, None


def _public_agent(agent: dict) -> dict:
    return {key: value for key, value in agent.items() if key not in _SENSITIVE_AGENT_FIELDS}


def _public_mission(mission: dict) -> dict:
    return {key: mission.get(key) for key in _PUBLIC_MISSION_FIELDS if key in mission}


def _visible_agent(subject: str, agent_id: str):
    visible = get_visible_agents(subject, list_agents())
    canonical_id, record = get_agent(agent_id)
    if record is None or canonical_id not in visible:
        return None, None
    return canonical_id, visible[canonical_id]


def register_mcp_bridge_routes(app):
    @app.route("/internal/mcp/v1/agents", methods=["GET"])
    def mcp_bridge_agents():
        subject, error = _require("agents.view_self")
        if error:
            return error
        visible = get_visible_agents(subject, list_agents())
        return jsonify({
            "agents": [_public_agent(item) for item in visible.values()],
        }), 200

    @app.route("/internal/mcp/v1/agents/<agent_id>", methods=["GET"])
    def mcp_bridge_agent(agent_id):
        subject, error = _require("agents.view_self")
        if error:
            return error
        canonical_id, record = _visible_agent(subject, str(agent_id))
        if record is None:
            return jsonify({"error": "AGENT_NOT_FOUND"}), 404
        return jsonify({"agent": _public_agent(record), "agent_id": canonical_id}), 200

    @app.route("/internal/mcp/v1/runtime/status", methods=["GET"])
    def mcp_bridge_runtime_status():
        _subject, error = _require("agents.view_self")
        if error:
            return error
        snapshot = runtime_status()
        return jsonify({
            "state": snapshot.get("state"),
            "running": snapshot.get("running"),
            "boot_ok": snapshot.get("boot_ok"),
            "queue_size": snapshot.get("queue_size"),
            "thread_alive": snapshot.get("thread_alive"),
            "agent_count": len(snapshot.get("agents", [])),
        }), 200

    @app.route("/internal/mcp/v1/state/fingerprint", methods=["GET"])
    def mcp_bridge_state_fingerprint():
        """Read-only, permission-gated fingerprint; never disclose database rows."""
        _subject, auth_error = _require("agents.view_self")
        if auth_error is not None:
            return auth_error

        try:
            snapshot = _local_state_fingerprint()
        except FileNotFoundError:
            return jsonify({"error": "STATE_FILE_MISSING"}), 503
        except Exception:
            # Do not echo file contents, paths from exceptions, or row values.
            return jsonify({"error": "STATE_FINGERPRINT_FAILED"}), 503

        response = jsonify({"ok": True, **snapshot})
        response.headers["Cache-Control"] = "no-store"
        return response, 200

    @app.route("/internal/mcp/v1/agents/<agent_id>/execute", methods=["POST"])
    def mcp_bridge_agent_execute(agent_id):
        subject, error = _require("agents.modify_self")
        if error:
            return error
        canonical_id, record = _visible_agent(subject, str(agent_id))
        if record is None:
            return jsonify({"error": "AGENT_NOT_FOUND"}), 404
        if str(subject) != str(record.get("owner_id")) and not has_permission(subject, "agents.manage"):
            return jsonify({"error": "AGENT_NOT_OWNED"}), 403
        payload = request.get_json(silent=True) or {}
        command = str(payload.get("command", "")).strip()
        if not command:
            return jsonify({"error": "COMMAND_REQUIRED"}), 400
        if len(command) > _MAX_COMMAND_LENGTH:
            return jsonify({"error": "COMMAND_TOO_LONG"}), 400
        try:
            result = execute_agent(canonical_id, command, source="mcp-bridge")
        except KeyError:
            return jsonify({"error": "AGENT_NOT_FOUND"}), 404
        except Exception as exc:
            return jsonify({"error": "AGENT_EXECUTION_FAILED", "type": type(exc).__name__}), 500
        return jsonify({"result": result}), 200

    @app.route("/internal/mcp/v1/missions", methods=["GET"])
    def mcp_bridge_missions():
        _subject, error = _require("public.view")
        if error:
            return error
        board, _manifest = MissionLifecycleService().load_state()
        if not isinstance(board, dict) or board.get("__invalid_state__"):
            return jsonify({"error": "MISSION_BOARD_UNAVAILABLE"}), 503
        return jsonify({
            "missions": [
                _public_mission(item)
                for item in board.get("missions", [])
                if isinstance(item, dict)
            ],
        }), 200

    @app.route("/internal/mcp/v1/missions/<mission_id>", methods=["GET"])
    def mcp_bridge_mission(mission_id):
        _subject, error = _require("public.view")
        if error:
            return error
        board, _manifest = MissionLifecycleService().load_state()
        mission = MissionLifecycleService().find_mission(board, str(mission_id))
        if mission is None:
            return jsonify({"error": "MISSION_NOT_FOUND"}), 404
        return jsonify({"mission": _public_mission(mission)}), 200

    @app.route("/internal/mcp/v1/missions/<mission_id>/complete", methods=["POST"])
    def mcp_bridge_mission_complete(mission_id):
        subject, error = _require("agents.modify_self")
        if error:
            return error
        lifecycle = MissionLifecycleService()
        board, manifest = lifecycle.load_state()
        mission = lifecycle.find_mission(board, str(mission_id))
        if mission is None:
            return jsonify({"error": "MISSION_NOT_FOUND"}), 404
        agent_id = str(mission.get("assigned_to") or "")
        canonical_id, agent = _visible_agent(subject, agent_id)
        if agent is None or canonical_id != agent_id:
            return jsonify({"error": "AGENT_NOT_VISIBLE"}), 403
        if str(subject) != str(agent.get("owner_id")) and not has_permission(subject, "agents.manage"):
            return jsonify({"error": "AGENT_NOT_OWNED"}), 403
        if str(mission.get("status", "")).lower() != "executed":
            return jsonify({
                "status": "blocked",
                "reason": "MISSION_NOT_EXECUTED",
                "current_status": mission.get("status"),
            }), 200
        result = lifecycle.complete_mission(str(mission_id))
        return jsonify(result), 200

    @app.route("/internal/mcp/v1/operator/preferences", methods=["GET", "PATCH"])
    def mcp_bridge_operator_preferences():
        permission = "agents.view_self" if request.method == "GET" else "agents.modify_self"
        subject, error = _require(permission)
        if error:
            return error
        from core.ui_preferences import get_preferences, set_preferences, validate_notification_level
        if request.method == "GET":
            prefs = get_preferences(subject)
            return jsonify({
                "ok": True,
                "notification_level": prefs["notification_level"],
                "allowed_levels": ["off", "milestones", "all"],
                "scope": "proactive_progress_updates_only",
            }), 200
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or set(payload.keys()) != {"notification_level"}:
            return jsonify({"error": "NOTIFICATION_PREFERENCE_PAYLOAD_INVALID"}), 400
        try:
            level = validate_notification_level(payload.get("notification_level"))
            prefs = set_preferences(subject, notification_level=level)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify({
            "ok": True,
            "notification_level": prefs["notification_level"],
            "scope": "proactive_progress_updates_only",
            "direct_command_replies_muted": False,
            "critical_security_messages_muted": False,
        }), 200
    return app
