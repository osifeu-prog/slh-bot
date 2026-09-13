from flask import Flask, jsonify, send_from_directory, request, make_response
import json
from pathlib import Path

from core.telegram_webapp_auth import validate_init_data
from core.investor_read_model import get_investor_snapshot
from core.alpha_control_plane import alpha_state
from core.wallet_binding import issue_challenge, verify_signature, get_binding

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "state" / "db.json"

app = Flask(__name__)


def load_db():
    if not DB_PATH.exists():
        return {}
    with DB_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


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
def mini_app():
    """Serve the Mini App with a tiny compatibility shim for guide buttons."""
    html_path = BASE_DIR / "mini_app.html"
    html = html_path.read_text(encoding="utf-8")
    shim = """
<script>
function showGuide(id){
  const el=document.getElementById(id);
  if(!el){return;}
  if(el.tagName.toLowerCase()==='details'){
    el.open=true;
    el.scrollIntoView({behavior:'smooth',block:'center'});
  }
}
</script>
"""
    if "function showGuide(" not in html:
        html = html.replace("</body>", shim + "</body>")
    resp = make_response(html)
    resp.headers["Content-Type"] = "text/html; charset=utf-8"
    return resp


@app.route("/api/v1/me")
def investor_me():
    """Return the read-only investor snapshot for the authenticated Telegram user."""
    uid = authenticated_uid()
    if uid is None:
        return jsonify({"error": "TELEGRAM_AUTH_REQUIRED"}), 401

    try:
        snapshot = get_investor_snapshot(uid)
        snapshot["alpha_global"] = alpha_state()
        if isinstance(snapshot.get("alpha"), dict):
            snapshot["alpha"]["global_status"] = snapshot["alpha_global"].get("status", "CLOSED")
        return jsonify(snapshot), 200
    except ValueError as exc:
        if str(exc) == "USER_NOT_FOUND":
            return jsonify({"error": "USER_NOT_FOUND"}), 404
        raise


@app.route("/api/wallet/<uid>")
def get_wallet(uid):
    denied = require_self(uid)
    if denied:
        return denied

    db = load_db()
    user = db.get("users", {}).get(str(uid), {})
    wallet = user.get("wallet", {})

    return jsonify({
        "name": user.get("name", str(uid)),
        "credits": wallet.get("credits", 0),
        "staked": wallet.get("staked", 0),
        "token_balance": wallet.get("token_balance", 0),
        "ton_wallet": user.get("ton_wallet")
    })


@app.route("/api/wallet/bnb/challenge", methods=["POST"])
def bnb_wallet_challenge():
    uid = authenticated_uid()