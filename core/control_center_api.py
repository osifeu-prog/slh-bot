from flask import jsonify, request
from core.control_center import get_system_snapshot, get_full_system_map, get_financial_truth
from core.telegram_webapp_auth import validate_init_data
from core.authority import has_permission


def _admin_uid():
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    try:
        uid = validate_init_data(init_data)["uid"]
    except (ValueError, RuntimeError):
        return None
    return uid if has_permission(uid, "exec.audit") else None


def register_control_center(app):

    @app.route("/control-center")
    def control_center():
        uid = _admin_uid()
        if uid is None:
            return jsonify({"error": "CONTROL_PLANE_AUTH_REQUIRED"}), 401
        return jsonify(get_full_system_map())

    @app.route("/api/financial-truth")
    def financial_truth():
        uid = _admin_uid()
        if uid is None:
            return jsonify({"error": "CONTROL_PLANE_AUTH_REQUIRED"}), 401
        return jsonify(get_financial_truth())

    @app.route("/api/system-map")
    def system_map():
        uid = _admin_uid()
        if uid is None:
            return jsonify({"error": "CONTROL_PLANE_AUTH_REQUIRED"}), 401
        return jsonify(get_full_system_map())
