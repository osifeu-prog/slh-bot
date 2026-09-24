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
(function(){
  // Public Mini App staking mutations are disabled; keep the UI read-only.
})();;
</script>
"""
    if "function showGuide(" not in html:
        html = html.replace("</body>", shim + "</body>")
    resp = make_response(html)
    resp.headers["Content-Type"] = "text/html; charset=utf-8"
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


@app.route("/api/v1/system/unified-map")
def unified_system_map():
    uid = authenticated_uid()
    if uid is None or not has_permission(uid, "exec.audit"):
        return jsonify({"error": "CONTROL_PLANE_AUTH_REQUIRED"}), 401
    return jsonify(get_unified_map()), 200


def _no_store(resp):
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


@app.route("/api/v1/me")
def investor_me():
    """Return the read-only investor snapshot for the authenticated Telegram user."""
    uid = authenticated_uid()
    if uid is None:
        return jsonify({"error": "TELEGRAM_AUTH_REQUIRED"}), 401

    try:
        snapshot = get_investor_snapshot(uid)
        global_alpha = alpha_state()
        if isinstance(snapshot.get("alpha"), dict):
            alpha = snapshot["alpha"]
            alpha["readiness_status"] = alpha.get("status", "review")
            alpha["global_status"] = global_alpha.get("status", "CLOSED")
            if alpha["global_status"] == "OPEN":
                alpha["status"] = "OPEN"
        snapshot["alpha_global"] = global_alpha
        return _no_store(jsonify(snapshot)), 200
    except ValueError as exc:
        if str(exc) == "USER_NOT_FOUND":
            return jsonify({"error": "USER_NOT_FOUND"}), 404
        raise


@app.route("/api/v1/staking", methods=["POST"])
def create_staking_position():
    """Public Mini App staking mutation is disabled; expose read-only status only."""
    return jsonify({
        "error": "STAKING_MUTATION_DISABLED",
        "message": "Staking actions are not enabled through the public Mini App.",
    }), 403

def _require_admin_api_key():
    expected = os.getenv("ADMIN_API_KEY", "").strip()
    supplied = request.headers.get("X-Admin-API-Key", "").strip()
    if not expected:
        return jsonify({"error": "ADMIN_API_NOT_CONFIGURED"}), 503
    if not supplied or not hmac.compare_digest(supplied, expected):
        return jsonify({"error": "FORBIDDEN"}), 403
    return None


@app.route("/api/v1/staking/revenue-share/status", methods=["GET"])
def staking_revenue_share_status():
    db = load_db()
    pool = db.get("revenue_share_pool", {})
    distributions = db.get("revenue_distributions", {})
    positions = db.get("staking_positions", {})
    active = sum(
        1 for pos in positions.values()
        if isinstance(pos, dict) and pos.get("status") == "active"
    ) if isinstance(positions, dict) else 0
    return jsonify({
        "pool": pool if isinstance(pool, dict) else {},
        "distribution_count": len(distributions) if isinstance(distributions, dict) else 0,
        "active_positions": active,
        "read_only": True,
    }), 200


@app.route("/api/v1/staking/revenue-share/distribute", methods=["POST"])
def staking_revenue_share_distribute():
    denied = _require_admin_api_key()
    if denied:
        return denied

    data = request.get_json(silent=True) or {}
    period_label = str(data.get("period_label", "")).strip()
    if not period_label:
        return jsonify({"error": "MISSING_PERIOD_LABEL"}), 400

    try:
        from core import staking_revenue_share as rs
        result = rs.distribute_revenue(
            data.get("gross_revenue", 0),
            data.get("operating_costs", 0),
            period_label,
        )
        return jsonify(result), 200
    except (TypeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception:
        return jsonify({"error": "SERVER_ERROR"}), 500
@app.route("/api/wallet/<uid>")
def get_wallet(uid):
    denied = require_self(uid)
    if denied:
        return denied

    db = load_db()
    user = db.get("users", {}).get(str(uid), {})
    wallet = user.get("wallet", {})

    return _no_store(jsonify({
        "name": user.get("name", str(uid)),
        "credits": wallet.get("credits", 0),
        "staked": wallet.get("staked", 0),
        "token_balance": wallet.get("token_balance", 0),
        "ton_wallet": user.get("ton_wallet")
    }))


@app.route("/api/v1/arcade/award", methods=["POST"])
def arcade_award():
    """Award Credits from arcade / skill-game play.

    Requires a valid arcade secret (ARCADE_API_KEY). Credits are marked
    with source="arcade" in the ledger meta so they can be distinguished
    from purchased Credits. This endpoint does NOT bypass economy_service.
    """
    import os
    expected = os.getenv("ARCADE_API_KEY", "").strip()
    if not expected:
        return jsonify({"error": "ARCADE_NOT_CONFIGURED"}), 503
    if request.headers.get("X-Arcade-Key", "").strip() != expected:
        return jsonify({"error": "FORBIDDEN"}), 403

    data = request.get_json(silent=True) or {}
    uid = str(data.get("uid", "")).strip()
    amount = data.get("amount")
    game_id = str(data.get("game_id", "")).strip()
    event_id = str(data.get("event_id", "")).strip()

    if not uid or not game_id or not event_id:
        return jsonify({"error": "MISSING_FIELDS"}), 400
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return jsonify({"error": "INVALID_AMOUNT"}), 400
    if amount <= 0 or amount > 10000:
        return jsonify({"error": "AMOUNT_OUT_OF_RANGE"}), 400

    from core import economy_service
    try:
        balance = economy_service.record_transaction(
            uid,
            amount,
            reason="arcade:award",
            meta={
                "source": "arcade",
                "game_id": game_id,
                "event_id": event_id,
                "idempotency_key": "arcade:" + game_id + ":" + event_id,
            },
        )
        return jsonify({
            "ok": True,
            "uid": uid,
            "awarded": amount,
            "balance": balance,
            "source": "arcade",
        }), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        print("[ARCADE] error:", type(e).__name__, str(e)[:200])
        return jsonify({"error": "SERVER_ERROR"}), 500


@app.route("/api/v1/wallet/combined/<uid>")
def combined_wallet(uid):
    """Read-only presentation adapter: internal ledger + slh-api ledger."""
    denied = require_self(uid)
    if denied:
        return denied

    db = load_db()
    user = db.get("users", {}).get(str(uid), {})
    wallet = user.get("wallet", {}) if isinstance(user, dict) else {}

    internal = {
        "credits": wallet.get("credits", 0),
        "staked": wallet.get("staked", 0),
        "slh": wallet.get("token_balance", 0),
        "ton_wallet": user.get("ton_wallet") if isinstance(user, dict) else None,
    }

    api_data = slh_api_client.get_balances(uid)

    return jsonify({
        "user_id": str(uid),
        "internal_ledger": internal,
        "api_ledger": api_data,
        "sources": {
            "internal": "state/db.json",
            "api": "slh-api/Postgres",
        },
        "read_only": True,
    })


@app.route("/api/wallet/bnb/challenge", methods=["POST"])
def bnb_wallet_challenge():
    uid = authenticated_uid()
    if uid is None:
        return jsonify({"error": "TELEGRAM_AUTH_REQUIRED"}), 401
    payload = request.get_json(silent=True) or {}
    try:
        result = issue_challenge(uid, payload.get("address"))
        return jsonify(result), 200
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/api/wallet/bnb/verify", methods=["POST"])
def bnb_wallet_verify():
    uid = authenticated_uid()
    if uid is None:
        return jsonify({"error": "TELEGRAM_AUTH_REQUIRED"}), 401
    payload = request.get_json(silent=True) or {}
    try:
        binding = verify_signature(uid, payload.get("address"), payload.get("signature"))
        return jsonify({"status": "verified", "binding": binding}), 200
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/api/wallet/bnb")
def bnb_wallet_binding():
    uid = authenticated_uid()
    if uid is None:
        return jsonify({"error": "TELEGRAM_AUTH_REQUIRED"}), 401
    return jsonify({"binding": get_binding(uid)}), 200


@app.route("/api/wallet/ton/challenge", methods=["POST"])
def ton_wallet_challenge():
    uid = authenticated_uid()
    if uid is None:
        return jsonify({"error": "TELEGRAM_AUTH_REQUIRED"}), 401
    payload = request.get_json(silent=True) or {}
    try:
        from core.ton_wallet_binding import issue_ton_challenge
        result = issue_ton_challenge(uid, domain=payload.get("domain"))
        return jsonify(result), 200
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/api/wallet/ton/verify", methods=["POST"])
def ton_wallet_verify():
    uid = authenticated_uid()
    if uid is None:
        return jsonify({"error": "TELEGRAM_AUTH_REQUIRED"}), 401
    payload = request.get_json(silent=True) or {}
    try:
        from core.ton_wallet_binding import verify_ton_proof
        binding = verify_ton_proof(uid, payload)
        return jsonify({"status": "verified", "binding": binding}), 200
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/api/wallet/ton")
def ton_wallet_binding():
    uid = authenticated_uid()
    if uid is None:
        return jsonify({"error": "TELEGRAM_AUTH_REQUIRED"}), 401
    from core.ton_deposit_service import _settings, deposits_are_open, memo_for
    from core.ton_wallet_binding import get_ton_binding
    treasury, rate = _settings()
    return jsonify({
        "binding": get_ton_binding(uid),
        "deposits_open": deposits_are_open(),
        "treasury": treasury,
        "credits_per_ton": float(rate),
        "memo": memo_for(uid),
    }), 200


@app.route("/api/wallet/ton/check", methods=["POST"])
def ton_wallet_check():
    uid = authenticated_uid()
    if uid is None:
        return jsonify({"error": "TELEGRAM_AUTH_REQUIRED"}), 401
    payload = request.get_json(silent=True) or {}
    tx_hash = str(payload.get("tx_hash", "")).strip()
    if not tx_hash:
        return jsonify({"error": "INVALID_TX_HASH"}), 400
    try:
        from core.ton_deposit_service import settle_ton_deposit
        result = settle_ton_deposit(uid, tx_hash)
        return jsonify(result), 200
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/api/tasks/<uid>")
def get_tasks(uid):
    denied = require_self(uid)
    if denied:
        return denied

    db = load_db()
    tasks = db.get("tasks", {})

    result = []

    for tid, task in tasks.items():
        if str(task.get('owner_id', '')) not in ('', str(uid)):
            continue
        done_by = task.get("done_by", [])

        result.append({
            "id": tid,
            "title": task.get("title", "?"),
            "reward": task.get("reward", 0),
            "status": (
                "done"
                if str(uid) in [str(x) for x in done_by]
                else task.get("status", "open")
            ),
            "agent": task.get("agent", "unassigned")
        })

    return jsonify(result)


@app.route("/api/stats")
def stats():
    denied = require_auth()
    if denied:
        return denied

    db = load_db()
    users = db.get("users", {})
    agents = db.get("agents", {})
    tasks = db.get("tasks", {})
    total_credits = 0

    if isinstance(users, dict):
        for user in users.values():
            if isinstance(user, dict):
                wallet = user.get("wallet", {})
                if isinstance(wallet, dict):
                    credits = wallet.get("credits", 0)
                    if isinstance(credits, (int, float)):
                        total_credits += credits

    return jsonify({
        "users": len(users) if isinstance(users, dict) else 0,
        "agents": len(agents) if isinstance(agents, dict) else 0,
        "tasks": len(tasks) if isinstance(tasks, dict) else 0,
        "credits": total_credits,
    })


@app.route("/api/leaderboard")
def api_leaderboard():
    denied = require_auth()
    if denied:
        return denied

    try:
        from plugins.leaderboard import LeaderboardPlugin

        lb = LeaderboardPlugin(str(DB_PATH))
        top = lb.get_top(10)

        result = []

        for uid, data in top:
            result.append({
                "uid": str(uid),
                "name": data.get("name", f"User{uid}"),
                "points": (data.get("gamification") or {}).get("points", 0)
            })

        return jsonify(result)

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500


@app.route("/api/v1/leaderboard")
def api_v1_leaderboard():
    return api_leaderboard()


@app.route("/api/onchain/status")
def onchain_status():
    denied = require_auth()
    if denied:
        return denied

    from core.deposit_monitor import get_onchain_status
    return jsonify(get_onchain_status())


# Read-only adapter over the existing exchange state. No order placement or settlement.
@app.route("/api/v1/exchange/markets")
def exchange_markets():
    return jsonify({"markets": [{"base": "SLH", "quote": "CREDITS", "symbol": "SLH/CREDITS"}]})


@app.route("/api/v1/exchange/orderbook")
def exchange_orderbook():
    db = load_db()
    raw = db.get("exchange_orders", {})
    orders = list(raw.values()) if isinstance(raw, dict) else (raw if isinstance(raw, list) else [])
    rows = []
    for order in orders:
        if not isinstance(order, dict) or order.get("status") != "open":
            continue
        rows.append({
            "id": order.get("id"),
            "side": order.get("side"),
            "amount": order.get("remaining_amount", order.get("original_amount")),
            "price": order.get("limit_price"),
            "created_at": order.get("created_at"),
        })
    rows.sort(key=lambda x: (x.get("created_at") or ""))
    return jsonify({"symbol": "SLH/CREDITS", "orders": rows})


@app.route("/api/v1/exchange/trades")
def exchange_trades():
    db = load_db()
    raw = db.get("exchange_trades", [])
    trades = raw if isinstance(raw, list) else []
    public_trades = []
    for trade in trades[-100:]:
        public_trades.append({
            "slh_amount": trade.get("slh_amount"),
            "price": trade.get("price"),
            "credits_value": trade.get("credits_value"),
            "timestamp": trade.get("timestamp"),
        })
    return jsonify({"symbol": "SLH/CREDITS", "trades": public_trades})


@app.route("/api/v1/exchange/ticker")
def exchange_ticker():
    db = load_db()
    raw = db.get("exchange_trades", [])
    trades = raw if isinstance(raw, list) else []
    if not trades:
        return jsonify({"symbol": "SLH/CREDITS", "has_data": False, "last_price": None})
    last = trades[-1]
    return jsonify({
        "symbol": "SLH/CREDITS",
        "has_data": True,
        "last_price": last.get("price"),
    })


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=8080
    )



@app.route("/api/v1/tokenomics")
def api_tokenomics():
    uid = authenticated_uid()
    if uid is None:
        return jsonify({"error": "TELEGRAM_AUTH_REQUIRED"}), 401
    try:
        from core.tokenomics import snapshot, rewards_snapshot
        from core.holiday_campaign import GRANT_AMOUNT, eligibility
        from core import profile_manager

        user = profile_manager.get_user(str(uid)) or {}
        points = int((user.get("gamification") or {}).get("points", 0) or 0)
        referrals = int((user.get("referral") or {}).get("count", 0) or 0)
        campaign = eligibility(str(uid))
        return jsonify({
            "tokenomics": snapshot(),
            "rewards": {
                **rewards_snapshot(),
                "task_rewards": "per_task",
            },
            "user": {
                "points": points,
                "successful_referrals": referrals,
                "holiday_referral": campaign,
            },
            "source_of_truth": "core/tokenomics.py + canonical reward engines",
            "read_only": True,
        }), 200
    except Exception as exc:
        return jsonify({"error": "INTERNAL_ERROR", "type": type(exc).__name__}), 500

@app.route("/api/v1/dashboard")
def api_dashboard():
    uid = authenticated_uid()
    if uid is None:
        return jsonify({"error": "TELEGRAM_AUTH_REQUIRED"}), 401
    try:
        from core.dashboard_read_model import get_dashboard
        return jsonify(get_dashboard(uid)), 200
    except ValueError as exc:
        if str(exc) == "USER_NOT_FOUND":
            return jsonify({"error": "USER_NOT_FOUND"}), 404
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": "INTERNAL_ERROR", "type": type(exc).__name__}), 500



@app.route("/api/v1/exchange/summary")
def api_exchange_summary():
    uid = authenticated_uid()
    if uid is None:
        return jsonify({"error": "TELEGRAM_AUTH_REQUIRED"}), 401
    try:
        from core.exchange_read_model import get_exchange_summary
        return jsonify(get_exchange_summary()), 200
    except Exception as exc:
        return jsonify({"error": "INTERNAL_ERROR", "type": type(exc).__name__}), 500



@app.route("/api/v1/exchange/order", methods=["POST"])
def api_exchange_order():
    uid = authenticated_uid()
    if uid is None:
        return jsonify({"error": "TELEGRAM_AUTH_REQUIRED"}), 401
    payload = request.get_json(silent=True) or {}
    side = str(payload.get("side", "")).strip().lower()
    request_id = str(payload.get("client_request_id", "")).strip()
    if side not in {"buy", "sell"}:
        return jsonify({"error": "INVALID_SIDE"}), 400
    if not request_id:
        return jsonify({"error": "MISSING_REQUEST_ID"}), 400
    try:
        from handlers.exchange_handler import _dec, _place, REQUESTS_KEY
        amount = _dec(payload.get("amount"), "amount")
        price = _dec(payload.get("price"), "price")
        key = f"WEBAPP-EXCHANGE-{uid}-{request_id}"

        def mutate(db):
            old = db.setdefault(REQUESTS_KEY, {}).get(key)
            if old is not None:
                return old
            return _place(db, str(uid), side, amount, price, key)

        result = state_manager.atomic_update(mutate)
        return jsonify(result), 200
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": "INTERNAL_ERROR", "type": type(exc).__name__}), 500


@app.route("/api/v1/exchange/order/<order_id>", methods=["DELETE"])
def api_exchange_cancel(order_id):
    uid = authenticated_uid()
    if uid is None:
        return jsonify({"error": "TELEGRAM_AUTH_REQUIRED"}), 401
    oid = str(order_id).strip()
    if not oid:
        return jsonify({"error": "MISSING_ORDER_ID"}), 400
    try:
        from handlers.exchange_handler import ORDERS_KEY, _wallet, _get, _set, _reserve, _set_reserve, _s, ZERO, _ledger, _assert_invariants

        def mutate(db):
            order = db.setdefault(ORDERS_KEY, {}).get(oid)
            if not order or str(order.get("uid")) != str(uid) or order.get("status") != "open":
                raise ValueError("ORDER_NOT_FOUND_OR_NOT_YOURS")
            wallet = _wallet(db, uid)
            remaining = __import__("decimal").Decimal(str(order["remaining_amount"]))
            if remaining <= ZERO:
                raise ValueError("ORDER_NOT_OPEN")
            if order["side"] == "sell":
                reserve = __import__("decimal").Decimal(str(order["reserved_slh"]))
                if reserve != remaining:
                    raise ValueError("ORDER_RESERVE_MISMATCH")
                _set_reserve(wallet, "exchange_reserved_slh", _reserve(wallet, "exchange_reserved_slh") - reserve)
                before = _get(wallet, "token_balance")
                _set(wallet, "token_balance", before + reserve)
                _ledger(db, uid, before, reserve, "exchange:cancel_release_slh", {"order_id": oid, "source": "webapp"})
                order["reserved_slh"] = _s(ZERO)
            else:
                reserve = __import__("decimal").Decimal(str(order["reserved_credits"]))
                expected = remaining * __import__("decimal").Decimal(str(order["limit_price"]))
                if reserve != expected:
                    raise ValueError("ORDER_RESERVE_MISMATCH")
                _set_reserve(wallet, "exchange_reserved_credits", _reserve(wallet, "exchange_reserved_credits") - reserve)
                before = _get(wallet, "credits")
                _set(wallet, "credits", before + reserve)
                _ledger(db, uid, before, reserve, "exchange:cancel_release_credits", {"order_id": oid, "source": "webapp"})
                order["reserved_credits"] = _s(ZERO)
            order["remaining_amount"] = _s(ZERO)
            order["status"] = "cancelled"
            _assert_invariants(db)
            return {"order_id": oid, "status": "cancelled"}

        return jsonify(state_manager.atomic_update(mutate)), 200
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": "INTERNAL_ERROR", "type": type(exc).__name__}), 500


@app.route("/api/v1/transfer", methods=["POST"])
def api_transfer():
    uid = authenticated_uid()
    if uid is None:
        return jsonify({"error": "TELEGRAM_AUTH_REQUIRED"}), 401
    payload = request.get_json(silent=True) or {}
    recipient = str(payload.get("recipient_uid", "")).strip()
    amount_raw = payload.get("amount")
    request_id = str(payload.get("client_request_id", "")).strip()
    if not recipient:
        return jsonify({"error": "MISSING_RECIPIENT"}), 400
    if not request_id:
        return jsonify({"error": "MISSING_REQUEST_ID"}), 400
    try:
        amount = float(amount_raw)
    except (TypeError, ValueError):
        return jsonify({"error": "INVALID_AMOUNT"}), 400
    if amount <= 0:
        return jsonify({"error": "INVALID_AMOUNT"}), 400
    idempotency_key = f"WEBAPP-TRANSFER-{uid}-{request_id}"
    try:
        from core import economy_service
        result = economy_service.transfer_credits(
            sender_uid=uid,
            recipient_uid=recipient,
            amount=amount,
            idempotency_key=idempotency_key,
            meta={"source": "miniapp"},
        )
        return jsonify(result), 200
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": "INTERNAL_ERROR", "type": type(exc).__name__}), 500




