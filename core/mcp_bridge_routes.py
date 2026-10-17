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
    @app.route("/internal/mcp/v1/miners", methods=["GET"])
    def mcp_bridge_miners():
        """Read safe telemetry from canonical registered ESP32 device records."""
        subject, error = _require("exec.audit")
        if error:
            return error
        try:
            from core.miner_service import list_registered_esp_devices, device_role_enabled
            devices = list_registered_esp_devices()
            result = []
            for device_id, device in sorted(devices.items()):
                owner_id = str(device.get("owner_id") or device.get("owner") or "")
                if owner_id != str(subject) and not has_permission(subject, "agents.manage"):
                    continue
                telemetry = device.get("telemetry")
                safe_telemetry = None
                if isinstance(telemetry, dict):
                    safe_telemetry = {
                        key: telemetry.get(key)
                        for key in (
                            "temperature_c", "watts", "volts", "amps", "energy_kwh",
                            "reported_status", "health_status", "alerts", "last_seen", "source",
                        )
                        if key in telemetry
                    }
                result.append({
                    "device_id": device_id,
                    "name": str(device.get("name") or device_id)[:80],
                    "type": str(device.get("type") or ""),
                    "status": str(device.get("status") or "unknown"),
                    "last_seen": device.get("last_seen"),
                    "last_telemetry_at": device.get("last_telemetry_at"),
                    "miner_enabled": bool(device_role_enabled(device_id, device)),
                    "telemetry": safe_telemetry,
                })
            return jsonify({"devices": result, "count": len(result), "read_only": True}), 200
        except Exception as exc:
            print("[MCP_BRIDGE] miner list error:", type(exc).__name__)
            return jsonify({"error": "MINER_STATUS_UNAVAILABLE"}), 503

    @app.route("/internal/mcp/v1/miners/<device_id>", methods=["GET"])
    def mcp_bridge_miner(device_id):
        """Read one registered ESP32 telemetry snapshot with owner scoping."""
        subject, error = _require("exec.audit")
        if error:
            return error
        try:
            from core.miner_service import get_registered_device, device_role_enabled
            device = get_registered_device(device_id)
            if not device or str(device.get("type", "") or "").strip().lower() not in {
                "esp32", "miner", "esp32_miner", "esp32-miner",
            }:
                return jsonify({"error": "DEVICE_NOT_FOUND"}), 404
            owner_id = str(device.get("owner_id") or device.get("owner") or "")
            if owner_id != str(subject) and not has_permission(subject, "agents.manage"):
                return jsonify({"error": "DEVICE_NOT_FOUND"}), 404
            telemetry = device.get("telemetry")
            safe_telemetry = None
            if isinstance(telemetry, dict):
                safe_telemetry = {
                    key: telemetry.get(key)
                    for key in (
                        "temperature_c", "watts", "volts", "amps", "energy_kwh",
                        "reported_status", "health_status", "alerts", "last_seen", "source",
                    )
                    if key in telemetry
                }
            return jsonify({
                "device_id": device_id,
                "name": str(device.get("name") or device_id)[:80],
                "type": str(device.get("type") or ""),
                "status": str(device.get("status") or "unknown"),
                "last_seen": device.get("last_seen"),
                "last_telemetry_at": device.get("last_telemetry_at"),
                "miner_enabled": bool(device_role_enabled(device_id, device)),
                "telemetry": safe_telemetry,
                "read_only": True,
            }), 200
        except Exception as exc:
            print("[MCP_BRIDGE] miner read error:", type(exc).__name__)
            return jsonify({"error": "MINER_STATUS_UNAVAILABLE"}), 503

    @app.route("/api/miner", methods=["POST"])
    def miner_telemetry_ingest():
        """Authenticated ESP32 telemetry receiver on the state-owning web service."""
        if request.content_length is not None and request.content_length > 8192:
            return jsonify({"error": "PAYLOAD_TOO_LARGE"}), 413
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "JSON_OBJECT_REQUIRED"}), 400

        try:
            from core.miner_service import MinerTelemetryError, ingest_telemetry

            record = ingest_telemetry(
                payload,
                authorization=request.headers.get("Authorization", ""),
            )
            return jsonify({
                "ok": True,
                "device_id": record["device_id"],
                "health_status": record["health_status"],
                "alerts": record["alerts"],
                "last_seen": record["last_seen"],
            }), 200
        except MinerTelemetryError as exc:
            return jsonify({"error": exc.code}), exc.status_code
        except Exception as exc:
            print("[MINER] telemetry ingest error:", type(exc).__name__)
            return jsonify({"error": "MINER_TELEMETRY_FAILED"}), 500

    return app
