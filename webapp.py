from flask import Flask, jsonify, send_from_directory, request, make_response
import state_manager
import hmac
import json
import os
import time
from pathlib import Path

from core.telegram_webapp_auth import validate_init_data
from core.authority import has_permission
from core.investor_read_model import get_investor_snapshot
from core.alpha_control_plane import alpha_state
from core.wallet_binding import issue_challenge, verify_signature, get_binding
from core import slh_api_client
from core.profile_manager import get_user
from core import staking_service
from handlers.unified_system_handler import get_unified_map
from core.mcp_bridge import register_mcp_bridge

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "state" / "db.json"

app = Flask(__name__)
register_mcp_bridge(app)


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

