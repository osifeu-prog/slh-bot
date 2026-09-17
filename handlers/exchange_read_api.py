from flask import jsonify


def register(app, load_db):
    """Register read-only HTTP adapters over the existing exchange state."""

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
        return jsonify({"symbol": "SLH/CREDITS", "trades": trades[-100:]})

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
