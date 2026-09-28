from core.asset_truth import build_slH_asset_truth


def test_legacy_internal_balance_is_not_promoted_to_live():
    truth = build_slH_asset_truth({
        "token_balance": 50000,
        "exchange_reserved_slh": 0,
    })

    assert truth["current_total"] == 50000
    assert truth["current_live"] == 0
    assert truth["current_reserved"] == 0
    assert truth["legacy_internal"] == 50000
    assert truth["spendable_live"] == 0
    assert truth["provenance_status"] == "legacy_internal"


def test_live_balance_excludes_reserved_amount_from_spendable():
    truth = build_slH_asset_truth({
        "token_balance": 120,
        "live_token_balance": 120,
        "exchange_reserved_slh": 30,
    })

    assert truth["current_total"] == 120
    assert truth["current_live"] == 120
    assert truth["current_reserved"] == 30
    assert truth["legacy_internal"] == 0
    assert truth["spendable_live"] == 90
    assert truth["provenance_status"] == "live_backed"


def test_empty_wallet_is_empty():
    truth = build_slH_asset_truth({})

    assert truth["current_total"] == 0
    assert truth["current_live"] == 0
    assert truth["current_reserved"] == 0
    assert truth["legacy_internal"] == 0
    assert truth["spendable_live"] == 0
    assert truth["provenance_status"] == "empty"
