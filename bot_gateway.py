import state_manager
from dotenv import load_dotenv
load_dotenv('.env')
import os, json, time, threading, traceback, sys
from pathlib import Path
import telebot
from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS

app = Flask(__name__)


def control_plane_uid():
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    try:
        uid = validate_init_data(init_data)["uid"]
    except (ValueError, RuntimeError):
        return None
    return uid if has_permission(uid, "exec.audit") else None


from core.control_center_api import register_control_center
from core.telegram_webapp_auth import validate_init_data
from core.authority import has_permission
from core.mcp_bridge_routes import register_mcp_bridge_routes
register_control_center(app)
register_mcp_bridge_routes(app)

try:
    from webapp import app as webapp_app
    for rule in webapp_app.url_map.iter_rules():
        if rule.rule == '/static/<path:filename>':
            continue
        if rule.rule == '/health':
            continue
        view = webapp_app.view_functions[rule.endpoint]
        app.add_url_rule(
            rule.rule,
            endpoint='webapp_' + rule.endpoint,
            view_func=view,
            methods=[m for m in rule.methods if m not in ('HEAD', 'OPTIONS')]
        )
    print('[SLH] WebApp routes mounted into gateway')
except Exception as e:
    print(f'[SLH] WebApp route mount failed: {e}')


@app.route('/health')
def health():
    return jsonify({"status": "ok", "service": "SLH OS Gateway"}), 200

@app.route('/api/agents')
def api_agents():
    if control_plane_uid() is None:
        return jsonify({"error": "CONTROL_PLANE_AUTH_REQUIRED"}), 401
    try:
        from core.agent_registry import STORE
        agents = STORE.get_all()
        result = {aid: {"name": a.get("name"), "state": a.get("state")} for aid, a in agents.items()}
        return jsonify({"total": len(agents), "agents": result}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/devices')
def api_devices():
    if control_plane_uid() is None:
        return jsonify({"error": "CONTROL_PLANE_AUTH_REQUIRED"}), 401
    try:
        import json
        with open("state/devices.json", encoding="utf-8") as f:
            data = json.load(f)
        return jsonify(data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/')
def index():
    return 'SLH OS Gateway', 200

@app.route('/dashboard')
def dashboard():
    return send_from_directory('web/dashboard_v2', 'index.html')