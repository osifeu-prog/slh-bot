from flask import Flask, jsonify, send_from_directory, request, make_response
import state_manager
import hmac
import json
import os
import time
from pathlib import Path

from core.telegram_webapp_auth import validate_init_data
from core.authority import has_permission
from core.control_plane_api import (
    authorize_internal, list_agents_control, get_agent_control, runtime_status_control,
    execute_agent_control, missions_list_control, mission_control, mission_complete_control,
    economy_balance_control, economy_ledger_control, economy_propose_control,
    economy_transfer_control, economy_reward_control,
)
from core.investor_read_model import get_investor_snapshot
from core.alpha_control_plane import alpha_state
from core.wallet_binding import issue_challenge, verify_signature, get_binding
from core import slh_api_client
from core.profile_manager import get_user
from core import staking_service
from handlers.unified_system_handler import get_unified_map

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "state" / "db.json"

app = Flask(__name__)


_AI_RATE_STATE = {}
_AI_RATE_WINDOW = 60
_AI_RATE_LIMIT = 20
_AI_ALLOWED_ORIGINS = {"https://slh.co.il", "https://slh-nft.com"}


def _ai_cors_response(response):
    origin = request.headers.get("Origin", "")
    if origin in _AI_ALLOWED_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Telegram-Init-Data"
        response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    return response


def _ai_rate_limited(key):
    now = time.monotonic()
    bucket = _AI_RATE_STATE.get(key)
    if bucket is None or now - bucket[0] >= _AI_RATE_WINDOW:
        _AI_RATE_STATE[key] = [now, 1]
        return False
    if bucket[1] >= _AI_RATE_LIMIT:
        return True
    bucket[1] += 1
    return False


@app.route("/api/ai/chat", methods=["POST", "OPTIONS"])
def canonical_ai_chat():
    """Public AI intake backed by the canonical SLH OS ask router.

    Telegram initData is optional for public website visitors. When supplied,
    it is server-validated and becomes the only trusted account identity.
    The JSON user_id field is never trusted for authorization.
    """
    if request.method == "OPTIONS":
        return _ai_cors_response(jsonify({"ok": True})), 204

    init_data = request.headers.get("X-Telegram-Init-Data", "").strip()
    uid = None
    if init_data:
        try:
            uid = validate_init_data(init_data)["uid"]
        except (ValueError, RuntimeError):
            return _ai_cors_response(jsonify({"error": "TELEGRAM_AUTH_INVALID"})), 401

    payload = request.get_json(silent=True) or {}
    message = str(payload.get("message", "")).strip()
    lang = str(payload.get("lang", "he")).strip().lower()[:8]
    if not message:
        return _ai_cors_response(jsonify({"error": "MISSING_MESSAGE"})), 400
    if len(message) > 2000:
        return _ai_cors_response(jsonify({"error": "MESSAGE_TOO_LONG"})), 400

    rate_key = f"uid:{uid}" if uid is not None else f"ip:{request.remote_addr or 'unknown'}"
    if _ai_rate_limited(rate_key):
        return _ai_cors_response(jsonify({"error": "RATE_LIMITED"})), 429

    question = message
    if lang and lang not in {"he", "iw"}:
        question = f"{message}\\n\\n[LANGUAGE_REQUEST] Respond in language code: {lang}."

    try:
        from core.ask_router import route
        reply = route(question, uid)
        if not reply:
            return _ai_cors_response(jsonify({"error": "AI_EMPTY_RESPONSE"})), 502
        response = jsonify({"reply": str(reply), "user_id": uid, "authenticated": uid is not None})
        return _ai_cors_response(response), 200
    except Exception as exc:
        print("[AI] canonical intake error:", type(exc).__name__, str(exc)[:200])
        return _ai_cors_response(jsonify({"error": "AI_UNAVAILABLE"})), 503


def load_db():
    """Read from the canonical state authority used by the rest of SLH OS."""
    return state_manager.load_db()


def authenticated_uid():
    """Return the Telegram UID authenticated by server-validated initData."""
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    try:
        return validate_init_data(init_data)["uid"]
    except (ValueError, RuntimeError):
        return None


def require_auth():
    """Require a valid Telegram Mini App identity for non-user-scoped APIs."""
    if authenticated_uid() is None:
        return jsonify({"error": "TELEGRAM_AUTH_REQUIRED"}), 401
    return None


def require_self(uid):
    authenticated = authenticated_uid()
    if authenticated is None:
        return jsonify({"error": "TELEGRAM_AUTH_REQUIRED"}), 401
    if str(uid) != authenticated:
        return jsonify({"error": "FORBIDDEN_USER_MISMATCH"}), 403
    return None


def _internal_control_plane_guard(permission):
    key = request.headers.get("X-SLH-Internal-Key", "")
    principal_id = request.headers.get("X-SLH-Principal-Id", "")
    if not authorize_internal(key, principal_id, permission):
        return jsonify({"error": "CONTROL_PLANE_INTERNAL_FORBIDDEN"}), 403
    return None


@app.route("/api/internal/control-plane/agents", methods=["GET"])
def internal_agents():
    denied = _internal_control_plane_guard("agents.view_all")
    if denied:
        return denied
    principal_id = request.headers.get("X-SLH-Principal-Id", "")
    return jsonify({"agents": list_agents_control(principal_id)}), 200


@app.route("/api/internal/control-plane/agents/<agent_id>", methods=["GET"])
def internal_agent(agent_id):
    denied = _internal_control_plane_guard("agents.view_all")
    if denied:
        return denied
    principal_id = request.headers.get("X-SLH-Principal-Id", "")
    try:
        return jsonify({"agent": get_agent_control(principal_id, agent_id)}), 200
    except KeyError:
        return jsonify({"error": "AGENT_NOT_FOUND"}), 404


@app.route("/api/internal/control-plane/runtime", methods=["GET"])
def internal_runtime():
    denied = _internal_control_plane_guard("agents.view_all")
    if denied:
        return denied
    principal_id = request.headers.get("X-SLH-Principal-Id", "")
    return jsonify(runtime_status_control(principal_id)), 200


@app.route("/api/internal/control-plane/agents/<agent_id>/execute", methods=["POST"])
def internal_agent_execute(agent_id):
    denied = _internal_control_plane_guard("agents.modify_self")
    if denied:
        return denied
    principal_id = request.headers.get("X-SLH-Principal-Id", "")
    payload = request.get_json(silent=True) or {}
    try:
        return jsonify(execute_agent_control(principal_id, agent_id, payload.get("command", ""))), 200
    except KeyError:
        return jsonify({"error": "AGENT_NOT_FOUND"}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/api/internal/control-plane/missions", methods=["GET"])
def internal_missions():
    denied = _internal_control_plane_guard("public.view")
    if denied:
        return denied
    principal_id = request.headers.get("X-SLH-Principal-Id", "")
    return jsonify({"missions": missions_list_control(principal_id)}), 200


@app.route("/api/internal/control-plane/missions/<mission_id>", methods=["GET"])
def internal_mission(mission_id):
    denied = _internal_control_plane_guard("public.view")
    if denied:
        return denied
    principal_id = request.headers.get("X-SLH-Principal-Id", "")
    try:
        return jsonify({"mission": mission_control(principal_id, mission_id)}), 200
    except KeyError:
        return jsonify({"error": "MISSION_NOT_FOUND"}), 404


@app.route("/api/internal/control-plane/missions/<mission_id>/complete", methods=["POST"])
def internal_mission_complete(mission_id):
    denied = _internal_control_plane_guard("agents.manage")
    if denied:
        return denied
    principal_id = request.headers.get("X-SLH-Principal-Id", "")
    try:
        return jsonify(mission_complete_control(principal_id, mission_id)), 200
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 403
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/api/internal/control-plane/economy/<agent_id>", methods=["GET"])
def internal_economy_balance(agent_id):
    denied = _internal_control_plane_guard("agents.view_all")
    if denied:
        return denied
    principal_id = request.headers.get("X-SLH-Principal-Id", "")
    try:
        return jsonify(economy_balance_control(principal_id, agent_id)), 200
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 403


@app.route("/api/internal/control-plane/economy/<agent_id>/ledger", methods=["GET"])
def internal_economy_ledger(agent_id):
    denied = _internal_control_plane_guard("agents.view_all")
    if denied:
        return denied
    principal_id = request.headers.get("X-SLH-Principal-Id", "")
    try:
        limit = int(request.args.get("limit", "100"))
        return jsonify({"ledger": economy_ledger_control(principal_id, agent_id, limit)}), 200
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 403
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/api/internal/control-plane/economy/propose", methods=["POST"])
def internal_economy_propose():
    denied = _internal_control_plane_guard("economy.mutate_self")
    if denied:
        return denied
    principal_id = request.headers.get("X-SLH-Principal-Id", "")
    data = request.get_json(silent=True) or {}
    try:
        return jsonify(economy_propose_control(
            principal_id, data.get("source_agent", ""), data.get("target_agent", ""),
            data.get("amount"), data.get("operation_id", ""), data.get("reason", "agent_transfer"),
        )), 200
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 403
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/api/internal/control-plane/economy/transfer", methods=["POST"])
def internal_economy_transfer():
    denied = _internal_control_plane_guard("economy.mutate_self")
    if denied:
        return denied
    principal_id = request.headers.get("X-SLH-Principal-Id", "")
    data = request.get_json(silent=True) or {}
    try:
        return jsonify(economy_transfer_control(
            principal_id, data.get("source_agent", ""), data.get("target_agent", ""),
            data.get("amount"), data.get("operation_id", ""), data.get("reason", "agent_transfer"),
        )), 200
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 403
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/api/internal/control-plane/economy/reward", methods=["POST"])
def internal_economy_reward():
    denied = _internal_control_plane_guard("agents.manage")
    if denied:
        return denied
    principal_id = request.headers.get("X-SLH-Principal-Id", "")
    data = request.get_json(silent=True) or {}
    try:
        return jsonify(economy_reward_control(
            principal_id, data.get("agent_id", ""), data.get("amount"),
            data.get("operation_id", ""), data.get("mission_id", ""),
        )), 200
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 403
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/health")
def health():
    return "OK", 200


@app.route("/market")
def market():
    return jsonify({
        "status": "SLH Market UP",
        "time": "2026-08-11"
    }), 200


@app.route("/mini-app")
@app.route("/mini-app-v2")
@app.route("/mini-app-v3")
@app.route("/mini-app-v4")
def mini_app():
    """Serve the Mini App with a compatibility and staking UX shim."""
    html_path = BASE_DIR / "mini_app.html"
    html = html_path.read_text(encoding="utf-8")