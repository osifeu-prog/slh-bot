from unittest.mock import patch

from core.bnb_history_audit import audit_bnb_deposit_history


TREASURY = "0x1111111111111111111111111111111111111111"
SENDER = "0x2222222222222222222222222222222222222222"
TX_HASH = "0x" + "a" * 64
AMOUNT_WEI = 10**16
OWNER_UID = "8789977826"


class FakeEth:
    chain_id = 56
    block_number = 100

    def __init__(self, sender=SENDER, destination=TREASURY, amount=AMOUNT_WEI, status=1):
        self.tx = {"from": sender, "to": destination, "value": amount}
        self.receipt = {"status": status, "blockNumber": 80}

    def get_transaction(self, tx_hash):
        result = dict(self.tx)
        result["hash"] = tx_hash
        return result

    def get_transaction_receipt(self, tx_hash):
        result = dict(self.receipt)
        result["transactionHash"] = tx_hash
        return result


def _fake_web3(eth):
    class FakeWeb3:
        @staticmethod
        def HTTPProvider(rpc, request_kwargs=None):
            return {"rpc": rpc, "request_kwargs": request_kwargs}

        def __init__(self, provider):
            self.eth = eth

    return FakeWeb3


def _db(*, sender=SENDER, destination=TREASURY, amount_wei=AMOUNT_WEI, duplicate=False):
    meta = {
        "tx_hash": TX_HASH,
        "idempotency_key": f"bnb:deposit:{TX_HASH.lower()}",
        "from": sender,
        "to": destination,
        "bnb_amount_wei": amount_wei,
        "bnb_amount": amount_wei / 10**18,
    }
    row = {
        "time": "2026-10-12T13:13:32+00:00",
        "uid": "owner",
        "reason": "bnb:deposit",
        "before": 18.091775,
        "amount": 10.0,
        "after": 28.091775,
        "meta": meta,
    }
    return {
        "users": {"owner": {"wallet": {"credits": 28.091775}}},
        "bsc_settings": {
            "chain_id": 56,
            "rpc": "https://rpc.example.invalid",
            "confirmations": 15,
            "treasury_wallet": TREASURY,
        },
        "wallet_bindings": {
            SENDER.lower(): {
                "uid": "owner",
                "chain": "bsc",
                "address": SENDER,
            }
        },
        "ledger": [row, dict(row) if duplicate else None] if duplicate else [row],
    }


def _run(db, fake_eth):
    with patch(
        "core.bnb_history_audit.get_bsc_config",
        return_value={
            "chain_id": 56,
            "rpc": "https://rpc.example.invalid",
            "confirmations": 15,
            "treasury_wallet": TREASURY,
        },
    ), patch("core.bnb_history_audit.Web3", _fake_web3(fake_eth)):
        return audit_bnb_deposit_history(db)


def test_clean_historical_bnb_deposit_passes():
    result = _run(_db(), FakeEth())
    assert result["status"] == "PASS"
    assert result["rows_found"] == 1
    assert result["rows_checked"] == 1
    assert result["failed_rows"] == 0
    assert result["findings"][0]["credits_match_chain"] is True


def test_self_transfer_is_not_accepted_as_a_historical_deposit():
    db = _db(sender=SENDER, destination=SENDER)
    result = _run(db, FakeEth(sender=SENDER, destination=SENDER))
    assert result["status"] == "BLOCKED"
    assert result["failed_rows"] == 1
    assert "SELF_TRANSFER_NOT_A_DEPOSIT" in result["findings"][0]["issues"]


def _add_audited_reversal(db):
    correction_key = f"accounting:reversal:{TX_HASH.lower()}"
    source_key = f"bnb:deposit:{TX_HASH.lower()}"
    source = db["ledger"][0]
    source_meta = source["meta"]
    source_meta["from"] = SENDER
    source_meta["to"] = SENDER
    db["bsc_settings"]["treasury_wallet"] = SENDER
    correction = {
        "time": "2026-10-12T13:14:00+00:00",
        "uid": "owner",
        "before": 28.091775,
        "amount": -10.0,
        "after": 18.091775,
        "reason": "accounting:invalid_bnb_deposit_reversal",
        "meta": {
            "idempotency_key": correction_key,
            "source_idempotency_key": source_key,
            "source_reason": "bnb:deposit",
            "source_ledger_index": 0,
            "tx_hash": TX_HASH.lower(),
            "actor_uid": OWNER_UID,
            "nominal_credits_reversed": 10.0,
            "chain_id": 56,
            "block": 80,
            "confirmations": 15,
            "required_confirmations": 15,
            "amount_wei": AMOUNT_WEI,
            "treasury": SENDER,
            "from": SENDER,
            "to": SENDER,
            "gate_remained_closed": True,
        },
    }
    db["ledger"].append(correction)
    db["credit_adjustment_audit"] = [{
        "event": "INVALID_BNB_SELF_TRANSFER_REVERSED",
        "uid": "owner",
        "actor_uid": OWNER_UID,
        "tx_hash": TX_HASH.lower(),
        "source_idempotency_key": source_key,
        "correction_idempotency_key": correction_key,
        "amount": -10.0,
        "nominal_credits_reversed": 10.0,
        "balance_before": 28.091775,
        "balance_after": 18.091775,
        "chain_id": 56,
        "block": 80,
        "confirmations": 15,
        "required_confirmations": 15,
        "gate_remained_closed": True,
    }]
    db["users"]["owner"]["wallet"]["credits"] = 18.091775
    return db


def test_self_transfer_stays_blocked_without_audited_reversal_even_if_destination_is_treasury():
    db = _db(sender=SENDER, destination=SENDER)
    db["bsc_settings"]["treasury_wallet"] = SENDER
    result = _run(db, FakeEth(sender=SENDER, destination=SENDER))

    assert result["status"] == "BLOCKED"
    assert "SELF_TRANSFER_NOT_A_DEPOSIT" in result["findings"][0]["issues"]


def test_complete_persisted_reversal_resolves_only_the_source_self_transfer():
    db = _add_audited_reversal(_db(sender=SENDER, destination=SENDER))
    result = _run(db, FakeEth(sender=SENDER, destination=SENDER))

    assert result["status"] == "PASS"
    assert result["failed_rows"] == 0
    assert result["findings"][0]["status"] == "RESOLVED_BY_AUDITED_REVERSAL"
    assert "RESOLVED_BY_AUDITED_REVERSAL" in result["findings"][0]["issues"]


def test_valid_reversal_remains_resolved_after_treasury_rotation():
    db = _add_audited_reversal(_db(sender=SENDER, destination=SENDER))
    # The treasury has since been rotated away from the historically recorded
    # self-transfer address. The persisted reversal must still reconcile from
    # its own historical metadata, not require the current treasury to match.
    db["bsc_settings"]["treasury_wallet"] = TREASURY
    result = _run(db, FakeEth(sender=SENDER, destination=SENDER))

    assert result["status"] == "PASS"
    assert result["failed_rows"] == 0
    assert result["findings"][0]["status"] == "RESOLVED_BY_AUDITED_REVERSAL"


def test_corrupt_reversal_audit_does_not_resolve_self_transfer():
    db = _add_audited_reversal(_db(sender=SENDER, destination=SENDER))
    db["credit_adjustment_audit"][0]["balance_after"] = 999.0
    result = _run(db, FakeEth(sender=SENDER, destination=SENDER))

    assert result["status"] == "BLOCKED"
    assert "SELF_TRANSFER_NOT_A_DEPOSIT" in result["findings"][0]["issues"]


def test_non_integer_reversal_metadata_does_not_resolve_self_transfer():
    db = _add_audited_reversal(_db(sender=SENDER, destination=SENDER))
    db["ledger"][1]["meta"]["block"] = 80.5
    result = _run(db, FakeEth(sender=SENDER, destination=SENDER))

    assert result["status"] == "BLOCKED"
    assert result["failed_rows"] == 1
    assert result["findings"][0]["status"] == "BLOCKED"


def test_duplicate_idempotency_key_blocks_audit():
    db = _db(duplicate=True)
    result = _run(db, FakeEth())
    assert result["status"] == "BLOCKED"
    assert result["failed_rows"] == 2
    assert "IDEMPOTENCY_KEY_NOT_UNIQUE" in result["blockers"]


def test_historic_receiver_different_from_current_treasury_requires_review():
    old_treasury = "0x3333333333333333333333333333333333333333"
    db = _db(destination=old_treasury)
    fake_eth = FakeEth(destination=old_treasury)
    result = _run(db, fake_eth)
    assert result["status"] == "BLOCKED"
    assert "HISTORICAL_DESTINATION_NOT_CURRENT_TREASURY" in result["blockers"]


def test_audit_fails_closed_when_ledger_shape_is_invalid():
    result = audit_bnb_deposit_history({"ledger": None})
    assert result["status"] == "BLOCKED"
    assert "LEDGER_UNREADABLE" in result["blockers"]
