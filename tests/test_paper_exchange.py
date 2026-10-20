from copy import deepcopy

from core import paper_exchange as paper


def _db():
    return {
        "users": {
            "100": {"wallet": {"credits": 17.0, "token_balance": 42.0}},
            "200": {"wallet": {"credits": 3.0, "token_balance": 9.0}},
        },
        "ledger": [
            {"uid": "100", "before": 17.0, "amount": 0, "after": 17.0, "reason": "test:anchor", "meta": {}}
        ],
        "exchange_orders": {"LIVE-1": {"id": "LIVE-1", "status": "open"}},
        "exchange_trades": [],
    }


def test_simulation_starts_in_its_own_namespace_only():
    db = _db()
    users_before = deepcopy(db["users"])
    ledger_before = deepcopy(db["ledger"])
    snapshot = paper.account_in_db(db, "100", now="2026-10-20T12:00:00+00:00")

    assert snapshot["demo_credits"] == "1000.00000000"
    assert snapshot["demo_slh"] == "1000.00000000"
    assert db["users"] == users_before
    assert db["ledger"] == ledger_before
    assert set(db["exchange_orders"]) == {"LIVE-1"}
    assert db["exchange_trades"] == []
    assert "paper_simulation" in db


def test_buy_uses_demo_credits_changes_pool_and_never_changes_real_ledger():
    db = _db()
    users_before = deepcopy(db["users"])
    ledger_before = deepcopy(db["ledger"])

    result = paper.trade_in_db(
        db, "100", "buy", "100", "telegram:1:1",
        now="2026-10-20T12:00:01+00:00",
    )

    assert result["status"] == "FILLED"
    assert result["trade"]["side"] == "buy"
    assert result["trade"]["fee_asset"] == "DEMO-CREDITS"
    assert result["trade"]["fee_amount"] == "0.30000000"
    assert float(result["trade"]["amount_slh"]) > 0
    assert result["account"]["demo_credits"] == "900.00000000"
    assert float(result["account"]["demo_slh"]) > 1000
    assert result["account"]["price_credits_per_slh"] != "1.00000000"
    assert db["users"] == users_before
    assert db["ledger"] == ledger_before
    assert len(db["paper_simulation"]["trades"]) == 1


def test_sell_uses_demo_slh_and_updates_only_simulation_namespace():
    db = _db()
    users_before = deepcopy(db["users"])
    ledger_before = deepcopy(db["ledger"])

    result = paper.trade_in_db(
        db, "100", "sell", "10", "telegram:1:2",
        now="2026-10-20T12:00:02+00:00",
    )

    assert result["status"] == "FILLED"
    assert result["trade"]["side"] == "sell"
    assert result["trade"]["fee_asset"] == "DEMO-SLH"
    assert result["trade"]["fee_amount"] == "0.03000000"
    assert result["account"]["demo_slh"] == "990.00000000"
    assert float(result["account"]["demo_credits"]) > 1000
    assert db["users"] == users_before
    assert db["ledger"] == ledger_before


def test_same_request_id_cannot_execute_the_trade_twice():
    db = _db()
    first = paper.trade_in_db(db, "100", "buy", "100", "telegram:1:99")
    balance_after_first = first["account"]["demo_credits"]
    trade_count = len(db["paper_simulation"]["trades"])
    pool_after_first = deepcopy(db["paper_simulation"]["pool"])

    second = paper.trade_in_db(db, "100", "buy", "100", "telegram:1:99")

    assert second["status"] == "FILLED"
    assert second["duplicate"] is True
    assert second["trade"]["id"] == first["trade"]["id"]
    assert second["account"]["demo_credits"] == balance_after_first
    assert len(db["paper_simulation"]["trades"]) == trade_count
    assert db["paper_simulation"]["pool"] == pool_after_first


def test_failed_trade_is_fail_closed_and_does_not_touch_real_wallet_or_ledger():
    db = _db()
    users_before = deepcopy(db["users"])
    ledger_before = deepcopy(db["ledger"])

    result = paper.trade_in_db(db, "100", "buy", "1001", "telegram:1:3")

    assert result["status"] == "BLOCKED"
    assert result["error"] == "INSUFFICIENT_DEMO_CREDITS"
    assert db["paper_simulation"]["trades"] == []
    assert db["users"] == users_before
    assert db["ledger"] == ledger_before


def test_invalid_amount_and_side_are_rejected():
    db = _db()
    assert paper.trade_in_db(db, "100", "buy", "NaN", "bad-1")["error"] == "INVALID_AMOUNT"
    assert paper.trade_in_db(db, "100", "transfer", "10", "bad-2")["error"] == "INVALID_SIDE"
    assert db["paper_simulation"]["trades"] == []


def test_history_and_leaderboard_are_scoped_and_do_not_expose_telegram_ids():
    db = _db()
    paper.trade_in_db(db, "100", "buy", "100", "r-1")
    paper.trade_in_db(db, "200", "sell", "5", "r-2")

    history = paper.history_in_db(db, "100")
    leaderboard = paper.leaderboard_in_db(db)

    assert len(history) == 1
    assert history[0]["uid"] == "100"
    assert len(leaderboard) == 2
    rendered = repr(leaderboard)
    assert "'100'" not in rendered
    assert "'200'" not in rendered
    assert all(row["alias"].startswith("Trader-") for row in leaderboard)


def test_paper_audit_reports_separation_and_duplicate_trade_ids():
    db = _db()
    assert paper.audit_in_db(db)["status"] == "EMPTY"
    paper.account_in_db(db, "100")
    assert paper.audit_in_db(db)["status"] == "PASS"
    db["paper_simulation"]["trades"] = [{"id": "X"}, {"id": "X"}]
    result = paper.audit_in_db(db)
    assert result["status"] == "BLOCKED"
    assert "duplicate_trade_id" in result["findings"]
    assert result["real_wallets_touched"] is False
    assert result["canonical_ledger_touched"] is False


def test_corrupt_paper_state_is_rejected_not_overwritten():
    db = {"users": {}, "paper_simulation": ["corrupt"]}
    try:
        paper.account_in_db(db, "100")
    except ValueError as exc:
        assert str(exc) == "PAPER_SIM_STATE_INVALID"
    else:
        raise AssertionError("invalid paper state should fail closed")
    assert db["paper_simulation"] == ["corrupt"]


def test_telegram_trade_receipt_renders_after_trade_pool_price():
    from handlers.simulation_handler import _trade_text

    db = _db()
    result = paper.trade_in_db(db, "100", "buy", "100", "receipt-1")
    rendered = _trade_text(result, "buy")

    assert "קנייה מדומה הושלמה" in rendered
    assert "שער pool אחרי העסקה" in rendered
    assert paper.compact(result["trade"]["price_after"]) in rendered
    assert "יתרות הדמו לאחר העסקה" in rendered


def test_telegram_receipt_renders_duplicate_without_second_execution():
    from handlers.simulation_handler import _trade_text

    db = _db()
    paper.trade_in_db(db, "100", "buy", "100", "receipt-duplicate")
    repeated = paper.trade_in_db(db, "100", "buy", "100", "receipt-duplicate")
    rendered = _trade_text(repeated, "buy")

    assert "זוהתה בקשה חוזרת" in rendered
    assert len(db["paper_simulation"]["trades"]) == 1
