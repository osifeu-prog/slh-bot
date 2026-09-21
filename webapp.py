

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

@app.route("/api/v1/earnings")
def api_earnings():
    uid = authenticated_uid()
    if uid is None:
        return jsonify({"error": "TELEGRAM_AUTH_REQUIRED"}), 401
    try:
        from core.earnings_read_model import get_earnings
        return _no_store(jsonify(get_earnings(uid))), 200
    except ValueError as exc:
        if str(exc) == "USER_NOT_FOUND":
            return jsonify({"error": "USER_NOT_FOUND"}), 404
        return jsonify({"error": str(exc)}), 400
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