from decimal import Decimal
from unittest.mock import patch

from core import ton_deposit_service


UID = "8789977826"
BOUND = "BOUND"
TREASURY = "TREASURY"
TX_HASH = "TON-TX-001"


def _response(rows):
    return type(
        "Response",
        (),
        {
            "raise_for_status": lambda self: None,
            "json": lambda self: {"ok": True, "result": rows},
        },
    )()


def _tx(*, memo="SLH8789977826", value=10_000_000):
    return {
        "transaction_id": {"hash": TX_HASH, "lt": "123"},
        "utime": 1791388200,
        "in_msg": {
            "source": BOUND,
            "destination": TREASURY,
            "value": str(value),
            "message": memo,
        },
    }


def test_canary_reconciliation_uses_canonical_settlement_path():
    with (
        patch.object(ton_deposit_service, "ton_settlement_allowed", return_value=True),
        patch.object(
            ton_deposit_service,
            "get_ton_binding",
            return_value={"uid": UID, "address": BOUND, "address_raw": BOUND},
        ),
        patch.object(
            ton_deposit_service,
            "_settings",
            return_value=(TREASURY, Decimal("100")),
        ),
        patch.object(ton_deposit_service, "normalize_ton_address", side_effect=lambda value: value),
        patch.object(
            ton_deposit_service.requests,
            "get",
            return_value=_response([_tx()]),
        ),
        patch.object(
            ton_deposit_service,
            "record_ton_deposit",
            return_value={"ledger_id": "ledger-1"},
        ) as record,
    ):
        result = ton_deposit_service.credit_new_ton_deposits(UID)

    assert len(result) == 1
    assert result[0]["tx_hash"] == TX_HASH
    assert result[0]["amount_ton"] == 0.01
    assert result[0]["credits"] == 1.0
    record.assert_called_once()


def test_wrong_memo_is_ignored_and_never_credited():
    with (
        patch.object(ton_deposit_service, "ton_settlement_allowed", return_value=True),
        patch.object(
            ton_deposit_service,
            "get_ton_binding",
            return_value={"uid": UID, "address": BOUND, "address_raw": BOUND},
        ),
        patch.object(
            ton_deposit_service,
            "_settings",
            return_value=(TREASURY, Decimal("100")),
        ),
        patch.object(ton_deposit_service, "normalize_ton_address", side_effect=lambda value: value),
        patch.object(
            ton_deposit_service.requests,
            "get",
            return_value=_response([_tx(memo="")]),
        ),
        patch.object(ton_deposit_service, "record_ton_deposit") as record,
    ):
        result = ton_deposit_service.credit_new_ton_deposits(UID)

    assert result == []
    record.assert_not_called()


def test_canary_without_binding_is_closed():
    with (
        patch.object(ton_deposit_service, "ton_settlement_allowed", return_value=True),
        patch.object(ton_deposit_service, "get_ton_binding", return_value=None),
    ):
        # canary permission alone must not be enough to settle funds
        try:
            ton_deposit_service.credit_new_ton_deposits(UID)
        except ValueError as exc:
            assert str(exc) == "TON_WALLET_NOT_VERIFIED"
        else:
            raise AssertionError("expected TON_WALLET_NOT_VERIFIED")
