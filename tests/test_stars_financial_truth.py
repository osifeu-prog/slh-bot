import core.stars_financial_truth as sft


def _db():
    return {
        "transactions": [
            {"uid": "501", "stars_paid": 100, "telegram_payment_charge_id": "tx-100"},
        ],
        "vip_subscriptions": {
            "tx-499": {"uid": "224", "stars": 499, "status": "ACTIVE"},
        },
        "star_item_orders": {
            "tx-199": {"uid": "884", "stars_paid": 199, "charge_id": "tx-199", "status": "FULFILLED"},
            "tx-025": {"uid": "224", "stars_paid": 25, "charge_id": "tx-025", "status": "FULFILLED"},
        },
        "revenue_ledger": [
            {"currency": "XTR", "amount": 100, "reference": "tx-100"},
            {"currency": "XTR", "amount": 499, "reference": "tx-499"},
            {"currency": "XTR", "amount": 199, "reference": "tx-199"},
            {"currency": "XTR", "amount": 25, "reference": "tx-025"},
            {"currency": "XTR", "amount": 100, "reference": "boundary-test-xtr", "meta": {"test": True}},
        ],
    }


def test_owner_live_reconciliation(monkeypatch):
    monkeypatch.setattr(sft.state_manager, "load_db", _db)

    def fake_telegram(method, params=None):
        if method == "getMyStarBalance":
            return {"amount": 823}
        if method == "getStarTransactions":
            return {"transactions": [
                {"id": "tx-100", "amount": 100, "date": 1,
                 "source": {"type": "user", "transaction_type": "invoice_payment",
                            "user": {"id": 501}}},
                {"id": "tx-499", "amount": 499, "date": 2,
                 "source": {"type": "user", "transaction_type": "invoice_payment",
                            "user": {"id": 224}}},
                {"id": "tx-199", "amount": 199, "date": 3,
                 "source": {"type": "user", "transaction_type": "invoice_payment",
                            "user": {"id": 884}}},
                {"id": "tx-025", "amount": 25, "date": 4,
                 "source": {"type": "user", "transaction_type": "invoice_payment",
                            "user": {"id": 224}}},
            ]}
        raise AssertionError(method)

    monkeypatch.setattr(sft, "_telegram", fake_telegram)
    result = sft.build_stars_financial_truth("878", owner=True)

    assert result["status"] == "LIVE_RECONCILED"
    assert result["owner"]["bot_stars_balance"] == 823
    assert result["owner"]["incoming_gross"] == 823
    assert result["owner"]["real_external_gross"] == 823
    assert result["owner"]["matched_count"] == 4
    assert result["owner"]["mismatch_count"] == 0
    assert result["owner"]["real_by_kind"] == {"store": 224, "vip": 499, "credits": 100}
    assert result["owner"]["test_legacy_xtr_revenue_gross"] == 100


def test_non_owner_view_does_not_call_telegram(monkeypatch):
    monkeypatch.setattr(sft.state_manager, "load_db", _db)

    def fail(*_args, **_kwargs):
        raise AssertionError("Telegram must not be called for non-owner")

    monkeypatch.setattr(sft, "_telegram", fail)
    result = sft.build_stars_financial_truth("224", owner=False)

    assert result["status"] == "LOCAL_PERSONAL_VIEW"
    assert result["personal"]["gross"] == 524
    assert result["personal"]["real_gross"] == 524
    assert result["personal"]["by_kind"] == {"store": 25, "vip": 499, "credits": 0}
