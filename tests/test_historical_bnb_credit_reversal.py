"""Tests for the dormant non-Treasury BNB self-transfer correction path."""
from copy import deepcopy
from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from core import historical_bnb_credit_reversal as target


UID = "test-owner-1"
TX = "0x" + "ab" * 32
VALID_TX = "0x" + "cd" * 32
WALLET = "0x2222222222222222222222222222222222222222"
TREASURY = "0x1111111111111111111111111111111111111111"
SOURCE_KEY = f"bnb:deposit:{TX}"
CORRECTION_KEY = f"accounting:reversal:{TX}"


def _db():
    return {
        "users": {UID: {"wallet": {"credits": 30.072775}}},
        "wallet_bindings": {
            "bsc:test-owner": {"uid": UID, "chain": "bsc", "address": WALLET}
        },
        "ledger": [
            {
                "uid": UID, "before": 7.091775, "amount": 1.0, "after": 8.091775,
                "reason": "test:seed", "meta": {},
            },
            {
                "uid": UID, "before": 8.091775, "amount": 10.0, "after": 18.091775,
                "reason": "bnb:deposit",
                "meta": {
                    "tx_hash": TX, "idempotency_key": SOURCE_KEY,
                    "bnb_amount_wei": 10**16, "from": WALLET, "to": WALLET,
                },
            },
            {
                "uid": UID, "before": 18.091775, "amount": 10.0, "after": 28.091775,
                "reason": "bnb:deposit",
                "meta": {
                    "tx_hash": VALID_TX, "idempotency_key": f"bnb:deposit:{VALID_TX}",
                    "bnb_amount_wei": 10**16, "from": WALLET, "to": TREASURY,
                },
            },
            {
                "uid": UID, "before": 28.091775, "amount": 0.99, "after": 29.081775,
                "reason": "exchange:settlement_credits", "meta": {},
            },
            {
                "uid": UID, "before": 29.081775, "amount": 0.991, "after": 30.072775,
                "reason": "exchange:settlement_credits", "meta": {},
            },
        ],
        "credit_adjustment_audit": [],
        "bsc_settings": {
            "chain_id": 56, "rpc": "https://rpc.invalid",
            "treasury_wallet": TREASURY, "confirmations": 15,
        },
    }


def _fake_web3(*, sender=WALLET, recipient=WALLET, status=1, value=10**16, block=80):
    fake = Mock()
    fake.eth.chain_id = 56
    fake.eth.block_number = 100
    fake.eth.get_transaction.return_value = {
        "hash": TX, "from": sender, "to": recipient, "value": value,
    }
    fake.eth.get_transaction_receipt.return_value = {
        "status": status, "blockNumber": block,
    }
    return fake


def _stub_web3(fake):
    class StubWeb3:
        HTTPProvider = staticmethod(lambda *_args, **_kwargs: object())

        def __new__(cls, *_args, **_kwargs):
            return fake

    return StubWeb3


def _patch_runtime(monkeypatch, db, *, fake=None):
    fake = fake or _fake_web3()
    monkeypatch.setenv("BNB_DEPOSITS_OPEN", "0")
    monkeypatch.setenv("SLH_BSC_CANONICAL_TREASURY", TREASURY)
    monkeypatch.setattr(target, "is_owner", lambda actor: str(actor) == UID)
    monkeypatch.setattr(target, "bnb_deposits_open", lambda: False)
    monkeypatch.setattr(target, "is_quarantined_bsc_address", lambda _address: False)
    monkeypatch.setattr(target, "_effective_config", lambda current: current["bsc_settings"])
    monkeypatch.setattr(target, "Web3", _stub_web3(fake))
    monkeypatch.setattr(target.state_manager, "load_db", lambda: db)
    monkeypatch.setattr(target.state_manager, "atomic_update", lambda mutate: mutate(db))
    return fake


def _apply(expected="30.072775"):
    return target.reverse_invalid_nontreasury_bnb_self_transfer(
        actor_uid=UID,
        uid=UID,
        tx_hash=TX,
        expected_current_balance=expected,
        now=datetime(2026, 10, 15, 9, 54, tzinfo=timezone.utc),
    )


def test_compensates_only_invalid_credit_and_preserves_later_activity(monkeypatch):
    db = _db()
    source_rows_before = deepcopy(db["ledger"])
    _patch_runtime(monkeypatch, db)

    result = _apply()

    assert result["status"] == "APPLIED"
    assert result["amount_reversed"] == 10.0
    assert result["balance_before"] == 30.072775
    assert result["balance_after"] == pytest.approx(20.072775)
    assert result["later_account_rows_preserved"] == 3
    assert result["gate_remained_closed"] is True
    assert db["users"][UID]["wallet"]["credits"] == pytest.approx(20.072775)
    assert db["ledger"][:len(source_rows_before)] == source_rows_before
    correction = db["ledger"][-1]
    assert correction["reason"] == "accounting:invalid_bnb_deposit_reversal"
    assert correction["before"] == pytest.approx(30.072775)
    assert correction["amount"] == -10.0
    assert correction["after"] == pytest.approx(20.072775)
    assert correction["meta"]["idempotency_key"] == CORRECTION_KEY
    assert correction["meta"]["source_idempotency_key"] == SOURCE_KEY
    assert correction["meta"]["adjustment_kind"] == "verified_invalid_nontreasury_bnb_self_transfer"
    assert correction["meta"]["source_ledger_rows_preserved"] is True
    assert len(db["credit_adjustment_audit"]) == 1
    assert db["credit_adjustment_audit"][0]["event"] == (
        "INVALID_BNB_NON_TREASURY_SELF_TRANSFER_REVERSED"
    )


def test_repeat_call_is_idempotent_even_with_original_expected_balance(monkeypatch):
    db = _db()
    _patch_runtime(monkeypatch, db)

    first = _apply()
    second = _apply("30.072775")

    assert first["status"] == "APPLIED"
    assert second["status"] == "ALREADY_REVERSED"
    assert db["users"][UID]["wallet"]["credits"] == pytest.approx(20.072775)
    assert len([r for r in db["ledger"] if isinstance(r.get("meta"), dict)
                 and r["meta"].get("idempotency_key") == CORRECTION_KEY]) == 1
    assert len(db["credit_adjustment_audit"]) == 1


def test_stale_expected_balance_fails_without_mutation(monkeypatch):
    db = _db()
    before = deepcopy(db)
    _patch_runtime(monkeypatch, db)

    with pytest.raises(ValueError, match="CURRENT_BALANCE_MISMATCH"):
        _apply("30.072774")

    assert db == before


def test_malformed_later_ledger_arithmetic_fails_without_mutation(monkeypatch):
    db = _db()
    db["ledger"][3]["amount"] = 1.0
    before = deepcopy(db)
    _patch_runtime(monkeypatch, db)

    with pytest.raises(ValueError, match="ACCOUNT_LEDGER_ARITHMETIC_FAILED"):
        _apply()

    assert db == before


def test_refuses_duplicate_user_wallet_binding(monkeypatch):
    db = _db()
    db["wallet_bindings"]["bsc:other-user"] = {
        "uid": "other-user", "chain": "bsc", "address": WALLET,
    }
    before = deepcopy(db)
    _patch_runtime(monkeypatch, db)

    with pytest.raises(ValueError, match="BNB_WALLET_BINDING_ADDRESS_NOT_UNIQUE"):
        _apply()

    assert db == before


def test_refuses_tx_that_is_not_bound_wallet_self_transfer(monkeypatch):
    db = _db()
    other = "0x3333333333333333333333333333333333333333"
    before = deepcopy(db)
    _patch_runtime(monkeypatch, db, fake=_fake_web3(sender=other, recipient=WALLET))

    with pytest.raises(ValueError, match="BNB_TX_NOT_BOUND_WALLET_SELF_TRANSFER"):
        _apply()

    assert db == before


def test_refuses_wallet_that_aliases_treasury_instead_of_this_case(monkeypatch):
    db = _db()
    db["wallet_bindings"]["bsc:test-owner"]["address"] = TREASURY
    db["ledger"][1]["meta"]["from"] = TREASURY
    db["ledger"][1]["meta"]["to"] = TREASURY
    before = deepcopy(db)
    _patch_runtime(monkeypatch, db, fake=_fake_web3(sender=TREASURY, recipient=TREASURY))

    with pytest.raises(ValueError, match="BNB_WALLET_ALIASES_TREASURY_NOT_THIS_CASE"):
        _apply()

    assert db == before


def test_historical_deposit_is_not_reconciled_without_separate_operator_approval(monkeypatch):
    db = _db()
    monkeypatch.delenv("SLH_BNB_RECONCILED_HISTORY_APPROVED", raising=False)

    assert target.is_reconciled_invalid_historical_deposit(
        db, 1, db["ledger"][1], _db()["bsc_settings"]
    ) is False


def test_refuses_when_operator_flag_is_on_even_if_historical_audit_blocks_gate(monkeypatch):
    db = _db()
    before = deepcopy(db)
    _patch_runtime(monkeypatch, db)
    monkeypatch.setenv("BNB_DEPOSITS_OPEN", "1")

    with pytest.raises(ValueError, match="BNB_OPERATOR_FLAG_MUST_BE_CLOSED"):
        _apply()

    assert db == before


def test_refuses_open_bnb_gate_without_mutation(monkeypatch):
    db = _db()
    before = deepcopy(db)
    _patch_runtime(monkeypatch, db)
    monkeypatch.setattr(target, "bnb_deposits_open", lambda: True)

    with pytest.raises(ValueError, match="BNB_GATE_MUST_REMAIN_CLOSED"):
        _apply()

    assert db == before


def test_orphan_audit_key_fails_closed(monkeypatch):
    db = _db()
    db["credit_adjustment_audit"].append({
        "event": "unexpected",
        "correction_idempotency_key": CORRECTION_KEY,
    })
    before = deepcopy(db)
    _patch_runtime(monkeypatch, db)

    with pytest.raises(ValueError, match="CREDIT_ADJUSTMENT_IDEMPOTENCY_CONFLICT"):
        _apply()

    assert db == before


def test_refuses_failed_onchain_receipt(monkeypatch):
    db = _db()
    before = deepcopy(db)
    _patch_runtime(monkeypatch, db, fake=_fake_web3(status=0))

    with pytest.raises(ValueError, match="BNB_TX_NOT_SUCCESSFUL"):
        _apply()

    assert db == before


def test_refuses_too_few_confirmations(monkeypatch):
    db = _db()
    before = deepcopy(db)
    _patch_runtime(monkeypatch, db, fake=_fake_web3(block=100))

    with pytest.raises(ValueError, match="BNB_TX_CONFIRMATIONS_INSUFFICIENT"):
        _apply()

    assert db == before
