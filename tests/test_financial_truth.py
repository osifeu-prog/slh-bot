import copy

import core.financial_truth as ft


def _db():
    return {
        "users": {
            "878": {
                "name": "Owner",
                "wallet": {
                    "credits": 8.191775,
                    "staked": 793,
                    "token_balance": 100,
                    "live_token_balance": 40,
                    "exchange_reserved_slh": 5,
                },
            }
        },
        "wallet_bindings": {
            "0xabc": {"uid": "878", "chain": "bsc", "address": "0xAbC"},
        },
        "ton_wallet_bindings": {
            "EQabc": {"uid": "878", "chain": "ton", "address": "EQabc"},
        },
        "ton_settings": {
            "wallet": "EQtreasury",
            "credits_per_ton": 100,
        },
    }


def _stars(_uid, owner=False):
    return {
        "generated_at": 1,
        "status": "LIVE_RECONCILED" if owner else "LOCAL_PERSONAL_VIEW",
        "scope": "owner" if owner else "personal",
        "owner": {
            "real_external_gross": 1122,
            "incoming_invoice_count": 6,
            "matched_count": 6,
        } if owner else None,
        "personal": {
            "real_gross": 25,
            "records": 1,
        },
    }


def test_unified_owner_model_is_read_only_and_separates_assets(monkeypatch):
    db = _db()
    original = copy.deepcopy(db)
    monkeypatch.setattr(ft.state_manager, "load_db", lambda: db)
    monkeypatch.setattr(
        ft,
        "bnb_readiness",
        lambda: {
            "flag_open": False,
            "ready": True,
            "effective_open": False,
            "chain_id": 56,
            "confirmations_required": 15,
            "reasons": [],
        },
    )
    monkeypatch.setattr(ft.os, "getenv", lambda key, default="": {
        "TON_DEPOSITS_OPEN": "0",
        "TON_CREDITS_PER_TON": "100",
        "TON_WALLET": "EQtreasury",
    }.get(key, default))

    result = ft.build_financial_truth("878", owner=True, stars_builder=_stars)

    assert result["schema"] == "financial_truth.v1"
    assert result["read_only"] is True
    assert result["internal"]["credits_available"] == 8.191775
    assert result["internal"]["credits_staked"] == 793
    assert result["rails"]["slh_live"]["current_total"] == 100
    assert result["rails"]["slh_live"]["current_live"] == 40
    assert result["rails"]["slh_live"]["current_reserved"] == 5
    assert result["rails"]["slh_live"]["spendable_live"] == 35
    assert result["rails"]["bnb"]["binding_status"] == "VERIFIED"
    assert result["rails"]["bnb"]["settlement_open"] is False
    assert result["rails"]["ton"]["binding_status"] == "VERIFIED"
    assert result["rails"]["ton"]["settlement_open"] is False
    assert result["stars"]["status"] == "LIVE_RECONCILED"
    assert result["reconciliation"]["blockers"] == [
        "BNB_SETTLEMENT_CLOSED",
        "TON_SETTLEMENT_CLOSED",
        # 40 live SLH exists, so there is no NO_SLH_LIVE_BALANCE blocker.
    ]
    assert db == original


def test_unified_personal_model_does_not_add_live_stars_reconciliation(monkeypatch):
    monkeypatch.setattr(ft.state_manager, "load_db", _db)
    monkeypatch.setattr(
        ft,
        "bnb_readiness",
        lambda: {
            "flag_open": False,
            "ready": False,
            "effective_open": False,
            "chain_id": 0,
            "confirmations_required": 15,
            "reasons": ["BSC_RPC_MISSING"],
        },
    )

    result = ft.build_financial_truth("878", owner=False, stars_builder=_stars)

    assert result["scope"] == "personal"
    assert result["stars"]["status"] == "LOCAL_PERSONAL_VIEW"
    assert result["stars"]["owner"] is None
    assert result["rails"]["bnb"]["binding_status"] == "VERIFIED"
    assert result["rails"]["bnb"]["settlement_open"] is False
    assert "BSC_RPC_MISSING" in result["rails"]["bnb"]["reasons"]
