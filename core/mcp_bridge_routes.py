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


def _whatsapp_store_principal():
    """Authenticate the separately scoped WhatsApp storefront service."""
    if os.getenv("WHATSAPP_STORE_ENABLED", "0").strip() != "1":
        return None, (jsonify({"error": "WHATSAPP_STORE_DISABLED"}), 404)

    expected = os.getenv("SLH_WHATSAPP_STORE_BRIDGE_TOKEN", "").strip()
    if not expected:
        return None, (jsonify({"error": "WHATSAPP_STORE_NOT_CONFIGURED"}), 503)

    authorization = request.headers.get("Authorization", "").strip()
    scheme, _, supplied = authorization.partition(" ")
    if scheme.lower() != "bearer" or not supplied or not hmac.compare_digest(supplied, expected):
        return None, (jsonify({"error": "WHATSAPP_STORE_AUTH_REQUIRED"}), 401)

    subject = os.getenv("SLH_WHATSAPP_STORE_PRINCIPAL_ID", "").strip()
    if not subject:
        return None, (jsonify({"error": "WHATSAPP_STORE_PRINCIPAL_NOT_CONFIGURED"}), 503)
    if not has_permission(subject, "whatsapp.store"):
        return None, (jsonify({"error": "WHATSAPP_STORE_FORBIDDEN"}), 403)
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

    @app.route("/internal/commerce/v1/whatsapp/catalog", methods=["GET"])
    def whatsapp_store_catalog():
        _subject, error = _whatsapp_store_principal()
        if error:
            return error
        try:
            from store.engine import load_items
            from store.stars_purchase_service import get_stars_items

            source_items = load_items()
            stars_items = get_stars_items()
            if not isinstance(source_items, dict) or not isinstance(stars_items, dict):
                raise RuntimeError("WHATSAPP_CATALOG_INVALID")
            public_items = []
            for raw_sku, raw_price in sorted(stars_items.items()):
                sku = str(raw_sku).strip()
                item = source_items.get(sku)
                if not sku or not isinstance(item, dict) or isinstance(raw_price, bool):
                    continue
                try:
                    price_stars = int(raw_price)
                except (TypeError, ValueError, OverflowError):
                    continue
                if price_stars <= 0:
                    continue
                raw_name = item.get("name")
                name = str(raw_name).strip()[:120] if isinstance(raw_name, str) and raw_name.strip() else sku
                raw_description = item.get("description")
                description = raw_description.strip()[:500] if isinstance(raw_description, str) else ""
                raw_type = item.get("type")
                item_type = str(raw_type).strip()[:40] if isinstance(raw_type, str) else "digital"
                public_items.append({
                    "sku": sku,
                    "name": name,
                    "description": description,
                    "type": item_type,
                    "price": price_stars,
                    "currency": "XTR",
                    "checkout_channel": "telegram_stars",
                })
            return jsonify({
                "items": public_items,
                "currency": "XTR",
                "checkout_channel": "telegram_stars",
                "payment_in_whatsapp": False,
            }), 200
        except Exception as exc:
            print("[WHATSAPP_STORE] catalog failed:", type(exc).__name__)
            return jsonify({"error": "WHATSAPP_CATALOG_UNAVAILABLE"}), 503

    @app.route("/internal/commerce/v1/whatsapp/intents", methods=["POST"])
    def whatsapp_store_purchase_intent():
        _subject, error = _whatsapp_store_principal()
        if error:
            return error

        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "JSON_OBJECT_REQUIRED"}), 400
        allowed_fields = {
            "provider", "provider_message_id", "sku", "intent", "customer_confirmed"
        }
        if set(payload) - allowed_fields:
            return jsonify({"error": "UNSUPPORTED_FIELDS"}), 400

        provider = str(payload.get("provider") or "").strip().lower()
        provider_message_id = str(payload.get("provider_message_id") or "").strip()
        sku = str(payload.get("sku") or "").strip()
        if provider != "twilio":
            return jsonify({"error": "PROVIDER_NOT_SUPPORTED"}), 400
        if (
            not provider_message_id
            or len(provider_message_id) > 255
            or not provider_message_id.isascii()
            or any(ord(char) < 33 or ord(char) > 126 for char in provider_message_id)
        ):
            return jsonify({"error": "INVALID_PROVIDER_MESSAGE_ID"}), 400
        if (
            not sku
            or len(sku) > 120
            or not sku.isascii()
            or any(not (char.isalnum() or char in "_-") for char in sku)
        ):
            return jsonify({"error": "INVALID_SKU"}), 400
        if payload.get("intent") != "purchase_inquiry" or payload.get("customer_confirmed") is not True:
            return jsonify({"error": "EXPLICIT_PURCHASE_INQUIRY_REQUIRED"}), 400

        try:
            from store.engine import load_items
            from store.stars_purchase_service import get_stars_items
            source_items = load_items()
            stars_items = get_stars_items()
            if not isinstance(source_items, dict) or not isinstance(stars_items, dict):
                raise RuntimeError("WHATSAPP_CATALOG_INVALID")
            item = source_items.get(sku)
            price_stars = stars_items.get(sku)
            if not isinstance(item, dict) or isinstance(price_stars, bool) or price_stars is None:
                return jsonify({"error": "SKU_NOT_AVAILABLE"}), 404
            price_stars = int(price_stars)
            if price_stars <= 0:
                return jsonify({"error": "SKU_NOT_AVAILABLE"}), 404

            import hashlib
            from datetime import datetime, timezone
            import state_manager

            idempotency_digest = hashlib.sha256(
                (provider + ":" + provider_message_id).encode("ascii")
            ).hexdigest()
            raw_name = item.get("name")
            item_name = str(raw_name).strip()[:120] if isinstance(raw_name, str) and raw_name.strip() else sku
            created_at = datetime.now(timezone.utc).isoformat()

            def mutate(db):
                intents = db.setdefault("whatsapp_purchase_intents", {})
                if not isinstance(intents, dict):
                    return {"status": "STATE_INVALID"}
                existing = intents.get(idempotency_digest)
                if existing is not None:
                    if (
                        not isinstance(existing, dict)
                        or str(existing.get("sku")) != sku
                        or str(existing.get("provider")) != provider
                    ):
                        return {"status": "CONFLICT"}
                    return {"status": "DUPLICATE", "intent": existing}
                if len(intents) >= 20000:
                    return {"status": "CAPACITY"}
                intent = {
                    "id": "WPI_" + idempotency_digest[:24],
                    "channel": "whatsapp",
                    "provider": provider,
                    "provider_message_id_hash": idempotency_digest,
                    "sku": sku,
                    "item_name": item_name,
                    "price_stars": price_stars,
                    "currency": "XTR",
                    "status": "inquiry_pending",
                    "financial_mutation": False,
                    "created_at": created_at,
                }
                intents[idempotency_digest] = intent
                return {"status": "CREATED", "intent": intent}

            result = state_manager.atomic_update(mutate)
            status = str(result.get("status") or "UNKNOWN") if isinstance(result, dict) else "UNKNOWN"
            if status == "CONFLICT":
                return jsonify({"error": "IDEMPOTENCY_CONFLICT"}), 409
            if status == "CAPACITY":
                return jsonify({"error": "WHATSAPP_INTENT_CAPACITY_REACHED"}), 503
            if status == "STATE_INVALID":
                return jsonify({"error": "WHATSAPP_INTENT_STATE_INVALID"}), 503
            if status not in {"CREATED", "DUPLICATE"}:
                return jsonify({"error": "WHATSAPP_INTENT_FAILED"}), 503
            intent = result["intent"]
            return jsonify({
                "ok": True,
                "intent_id": intent["id"],
                "status": intent["status"],
                "sku": intent["sku"],
                "price": intent["price_stars"],
                "currency": intent["currency"],
                "checkout_channel": "telegram_stars",
                "payment_in_whatsapp": False,
                "financial_mutation": False,
                "duplicate": status == "DUPLICATE",
            }), 200
        except Exception as exc:
            print("[WHATSAPP_STORE] inquiry failed:", type(exc).__name__)
            return jsonify({"error": "WHATSAPP_INTENT_FAILED"}), 503

    return app
