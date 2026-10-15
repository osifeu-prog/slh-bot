import os
from unittest.mock import Mock, patch

from core.bnb_gate import bnb_deposits_open, bnb_opening_evidence, bnb_settlement_allowed


TREASURY = "0x1111111111111111111111111111111111111111"


def _cfg():
    return {
        "network": "bsc",
        "rpc": "https://example.invalid",
        "chain_id": 56,
        "confirmations": 15,
        "treasury_wallet": TREASURY,
    }


def test_bnb_opening_evidence_is_read_only_and_blocks_without_empirical_proof():
    with patch.dict(
        os.environ,
        {
            "BNB_DEPOSITS_OPEN": "0",
            "SLH_BSC_CANONICAL_TREASURY": TREASURY,
        },
        clear=False,
    ), patch("core.bnb_gate._effective_config", return_value=_cfg()), patch(
        "core.deposit_monitor.get_onchain_status",
        return_value={
            "ok": True,
            "chain_id": 56,
            "block": 123,
            "treasury_wallet": TREASURY,
            "network": "bsc",
        },
    ):
        status = bnb_opening_evidence()

    assert status["scope"] == "read_only"
    assert status["ready_to_open"] is False
    assert status["status"] == "BLOCKED"
    assert status["gate_open"] is False
    assert status["live_rpc"]["status"] == "PASS"
    assert status["checks"]["wallet_binding"]["status"] == "PENDING_EMPIRICAL"
    assert status["checks"]["tx_verification"]["status"] == "PENDING_EMPIRICAL"
    assert status["checks"]["idempotency"]["status"] == "PENDING_EMPIRICAL"
    assert status["checks"]["atomic_ledger"]["status"] == "PENDING_EMPIRICAL"
    assert status["checks"]["reconciliation"]["status"] == "PENDING_EMPIRICAL"


def test_bnb_opening_evidence_blocks_when_live_rpc_is_not_verified():
    with patch.dict(
        os.environ,
        {
            "BNB_DEPOSITS_OPEN": "0",
            "SLH_BSC_CANONICAL_TREASURY": TREASURY,
        },
        clear=False,
    ), patch("core.bnb_gate._effective_config", return_value=_cfg()), patch(
        "core.deposit_monitor.get_onchain_status",
        return_value={"ok": False, "error": "treasury read unavailable"},
    ), patch(
        "core.deposit_monitor.probe_bsc_rpc",
        return_value={"ok": False, "error": "BSC_RPC_PROBE_FAILED"},
    ):
        status = bnb_opening_evidence()

    assert status["status"] == "BLOCKED"
    assert status["ready_to_open"] is False
    assert status["live_rpc"]["status"] == "FAIL"
    assert "LIVE_BSC_RPC_UNVERIFIED" in status["blockers"]


def test_bnb_opening_evidence_rejects_forged_pass_without_complete_evidence():
    forged = {"status": "PASS", "tx_hash": "not-a-real-hash"}
    with patch.dict(
        os.environ,
        {
            "BNB_DEPOSITS_OPEN": "0",
            "SLH_BSC_CANONICAL_TREASURY": TREASURY,
        },
        clear=False,
    ), patch("core.bnb_gate._effective_config", return_value=_cfg()), patch(
        "core.bnb_gate._empirical_settlement_evidence", return_value=forged
    ), patch(
        "core.deposit_monitor.get_onchain_status",
        return_value={
            "ok": True,
            "chain_id": 56,
            "block": 123,
            "treasury_wallet": TREASURY,
            "network": "bsc",
        },
    ):
        status = bnb_opening_evidence()

    assert status["status"] == "BLOCKED"
    assert status["ready_to_open"] is False
    assert status["checks"]["wallet_binding"]["status"] == "PENDING_EMPIRICAL"
    assert status["checks"]["tx_verification"]["status"] == "PENDING_EMPIRICAL"


def test_empirical_evidence_shape_rejects_missing_checks():
    from core.bnb_gate import _empirical_evidence_shape_valid

    assert _empirical_evidence_shape_valid({"status": "PASS"}) is False



def test_complete_live_evidence_is_revalidated_but_gate_stays_closed():
    tx_hash = "0x" + "a" * 64
    wallet = "0x2222222222222222222222222222222222222222"
    amount_wei = 10**16  # 0.01 BNB -> 10 Credits
    empirical = {
        "status": "PASS",
        "tx_hash": tx_hash,
        "observed_at": "2026-10-09T07:00:00+00:00",
        "amount_wei": amount_wei,
        "confirmations": 15,
        "ledger_entries_for_idempotency_key": 1,
        "credits": 10.0,
        "balance_before": 100.0,
        "balance_after": 110.0,
        "replay_balance_after": 110.0,
        "checks": {
            "wallet_binding": True,
            "tx_verification": True,
            "idempotency": True,
            "atomic_ledger": True,
            "reconciliation": True,
        },
        "from_bound_wallet": True,
        "gate_remained_closed": True,
        "uid": "224223270",
        "to_treasury": TREASURY,
    }
    db = {
        "wallet_bindings": {
            wallet.lower(): {
                "uid": "224223270",
                "chain": "bsc",
                "address": wallet,
            }
        },
        "ledger": [{
            "uid": "224223270",
            "reason": "bnb:deposit",
            "amount": 10.0,
            "before": 100.0,
            "after": 110.0,
            "meta": {
                "idempotency_key": f"bnb:deposit:{tx_hash.lower()}",
                "tx_hash": tx_hash,
                "bnb_amount_wei": amount_wei,
                "from": wallet,
                "to": TREASURY,
            },
        }]
    }
    verified = {
        "ok": True,
        "tx_hash": tx_hash,
        "from": wallet,
        "to": TREASURY,
        "amount_wei": amount_wei,
        "confirmations": 15,
    }

    with patch.dict(
        os.environ,
        {
            "BNB_DEPOSITS_OPEN": "0",
            "SLH_BSC_CANONICAL_TREASURY": TREASURY,
        },
        clear=False,
    ), patch("core.bnb_gate._effective_config", return_value=_cfg()), patch(
        "core.deposit_monitor.get_onchain_status",
        return_value={
            "ok": True,
            "chain_id": 56,
            "block": 123,
            "treasury_wallet": TREASURY,
            "network": "bsc",
        },
    ), patch(
        "core.bnb_gate._empirical_settlement_evidence", return_value=empirical
    ), patch(
        "core.deposit_monitor.verify_bnb_deposit", return_value=verified
    ) as live_tx_check, patch(
        "core.wallet_binding.get_binding", return_value={"address": wallet}
    ) as binding_lookup, patch(
        "state_manager.load_db", return_value=db
    ) as ledger_load:
        status = bnb_opening_evidence()

    assert live_tx_check.call_count == 2
    live_tx_check.assert_called_with(tx_hash)
    assert binding_lookup.call_count == 2
    binding_lookup.assert_called_with("224223270")
    assert ledger_load.call_count == 1
    assert status["status"] == "READY_TO_OPEN"
    assert status["ready_to_open"] is True
    assert status["empirical_settlement"]["status"] == "PASS"
    assert status["empirical_settlement"]["tx_hash"] == tx_hash
    assert status["gate_open"] is False
    assert status["next_action"] == "operator_may_review_bnb_gate_opening"


def test_operator_flag_and_forged_pass_do_not_open_public_bnb_settlement():
    forged = {"status": "PASS", "tx_hash": "not-a-real-hash"}
    with patch.dict(
        os.environ,
        {
            "BNB_DEPOSITS_OPEN": "1",
            "BNB_DEPOSITS_CANARY_UID": "8789977826",
            "SLH_BSC_CANONICAL_TREASURY": TREASURY,
        },
        clear=False,
    ), patch("core.bnb_gate._effective_config", return_value=_cfg()), patch(
        "core.bnb_gate._empirical_settlement_evidence", return_value=forged
    ):
        assert bnb_deposits_open() is False
        assert bnb_settlement_allowed("224223270") is False


def test_bnb_quarantined_treasury_does_not_claim_rpc_failed():
    quarantined = "0x693db6c817083818696a7228aebfbd0cd3371f02"
    cfg = {**_cfg(), "treasury_wallet": quarantined}
    with patch.dict(
        os.environ,
        {
            "BNB_DEPOSITS_OPEN": "0",
            "SLH_BSC_CANONICAL_TREASURY": quarantined,
        },
        clear=False,
    ), patch("core.bnb_gate._effective_config", return_value=cfg), patch(
        "core.deposit_monitor.get_onchain_status",
        return_value={
            "ok": False,
            "error": "BSC_ADDRESS_QUARANTINED_ZUZ",
            "forensic_alias": "ZUZ",
            "forensic_read_only": True,
        },
    ), patch(
        "core.deposit_monitor.probe_bsc_rpc",
        return_value={"ok": True, "chain_id": 56, "block": 123, "network": "bsc"},
    ):
        status = bnb_opening_evidence()

    assert status["live_rpc"]["status"] == "PASS"
    assert status["live_rpc"]["chain_id"] == 56
    assert status["live_rpc"]["block"] == 123
    assert status["treasury_snapshot"]["status"] == "NOT_CHECKED"
    assert "LIVE_BSC_RPC_UNVERIFIED" not in status["blockers"]
    assert "BNB_TREASURY_QUARANTINED_ZUZ" in status["blockers"]
    assert status["ready_to_open"] is False
    assert status["status"] == "BLOCKED"


def test_probe_bsc_rpc_reads_chain_and_block_without_touching_treasury(monkeypatch):
    from core import deposit_monitor

    quarantined = "0x693db6c817083818696a7228aebfbd0cd3371f02"
    config = {**_cfg(), "treasury_wallet": quarantined}
    fake_w3 = Mock()
    fake_w3.eth.chain_id = 56
    fake_w3.eth.block_number = 123456
    fake_web3_class = Mock(return_value=fake_w3)
    provider = Mock(return_value=object())
    fake_web3_class.HTTPProvider = provider

    with patch("core.deposit_monitor.get_bsc_config", return_value=config), patch(
        "core.deposit_monitor.state_manager.load_db",
        return_value={"bsc_settings": {"treasury_wallet": quarantined}},
    ), patch("core.deposit_monitor.Web3", fake_web3_class):
        result = deposit_monitor.probe_bsc_rpc()

    assert result["ok"] is True
    assert result["chain_id"] == 56
    assert result["block"] == 123456
    assert result["network"] == "bsc"
    provider.assert_called_once_with(config["rpc"], request_kwargs={"timeout": 5})


def _historical_deposit_fixture():
    tx_hash = "0x" + "a" * 64
    bad_hash = "0x" + "b" * 64
    wallet = "0x2222222222222222222222222222222222222222"
    amount_wei = 10**16
    empirical = {
        "status": "PASS",
        "tx_hash": tx_hash,
        "observed_at": "2026-10-09T07:00:00+00:00",
        "amount_wei": amount_wei,
        "confirmations": 15,
        "ledger_entries_for_idempotency_key": 1,
        "credits": 10.0,
        "balance_before": 18.091775,
        "balance_after": 28.091775,
        "replay_balance_after": 28.091775,
        "checks": {
            "wallet_binding": True,
            "tx_verification": True,
            "idempotency": True,
            "atomic_ledger": True,
            "reconciliation": True,
        },
        "from_bound_wallet": True,
        "gate_remained_closed": True,
        "uid": "224223270",
        "to_treasury": TREASURY,
    }
    good_entry = {
        "uid": "224223270",
        "reason": "bnb:deposit",
        "amount": 10.0,
        "before": 18.091775,
        "after": 28.091775,
        "meta": {
            "idempotency_key": f"bnb:deposit:{tx_hash.lower()}",
            "tx_hash": tx_hash,
            "bnb_amount_wei": amount_wei,
            "from": wallet,
            "to": TREASURY,
        },
    }
    bad_entry = {
        "uid": "224223270",
        "reason": "bnb:deposit",
        "amount": 10.0,
        "before": 8.091775,
        "after": 18.091775,
        "meta": {
            "idempotency_key": f"bnb:deposit:{bad_hash.lower()}",
            "tx_hash": bad_hash,
            "bnb_amount_wei": amount_wei,
            "from": wallet,
            "to": wallet,
        },
    }
    db = {
        "bsc_settings": _cfg(),
        "wallet_bindings": {
            wallet.lower(): {
                "uid": "224223270",
                "chain": "bsc",
                "address": wallet,
            }
        },
        "settlement_evidence": {"bnb": empirical},
        "ledger": [bad_entry, good_entry],
    }
    verified = {
        "ok": True,
        "tx_hash": tx_hash,
        "from": wallet,
        "to": TREASURY,
        "amount_wei": amount_wei,
        "confirmations": 15,
    }
    return db, empirical, tx_hash, bad_hash, wallet, verified


def _verify_fixture_tx(tx_hash, valid_hash, verified):
    if str(tx_hash).lower() == str(valid_hash).lower():
        return dict(verified)
    return {
        "ok": False,
        "error": "BNB_SELF_TRANSFER_NOT_DEPOSIT",
        "from": verified["from"],
        "to": verified["from"],
        "tx_hash": str(tx_hash),
    }



def test_historical_self_transfer_with_valid_compensation_is_reconciled_only_for_specific_error():
    from core.bnb_gate import _audit_historical_bnb_deposits

    db, empirical, tx_hash, bad_hash, wallet, verified = _historical_deposit_fixture()

    def verify_one(tx):
        if str(tx).lower() == tx_hash.lower():
            return dict(verified)
        return {
            "ok": False,
            "error": "BNB_TX_RECIPIENT_NOT_TREASURY",
            "to": wallet,
            "treasury": TREASURY,
        }

    with patch.dict(os.environ, {"SLH_BNB_RECONCILED_HISTORY_APPROVED": "1"}, clear=False), patch(
        "core.bnb_gate._effective_config", return_value=_cfg()
    ), patch(
        "core.deposit_monitor.verify_bnb_deposit", side_effect=verify_one
    ), patch(
        "core.wallet_binding.get_binding", return_value={"address": wallet}
    ), patch(
        "core.historical_bnb_credit_reversal.is_reconciled_invalid_historical_deposit",
        return_value=True,
    ) as valid_compensation:
        result = _audit_historical_bnb_deposits(db, _cfg())

    assert result["ok"] is True
    assert result["rows_checked"] == 2
    assert result["reconciled_count"] == 1
    assert result["finding_count"] == 0
    assert result["findings"] == []
    valid_compensation.assert_called_once_with(db, 0, db["ledger"][0], _cfg())


def test_historical_self_transfer_compensation_cannot_mask_other_ledger_findings():
    from core.bnb_gate import _audit_historical_bnb_deposits

    db, empirical, tx_hash, bad_hash, wallet, verified = _historical_deposit_fixture()
    db["ledger"][0]["meta"]["idempotency_key"] = "bnb:deposit:wrong"

    def verify_one(tx):
        if str(tx).lower() == tx_hash.lower():
            return dict(verified)
        return {
            "ok": False,
            "error": "BNB_TX_RECIPIENT_NOT_TREASURY",
            "to": wallet,
            "treasury": TREASURY,
        }

    with patch.dict(os.environ, {"SLH_BNB_RECONCILED_HISTORY_APPROVED": "1"}, clear=False), patch(
        "core.bnb_gate._effective_config", return_value=_cfg()
    ), patch(
        "core.deposit_monitor.verify_bnb_deposit", side_effect=verify_one
    ), patch(
        "core.wallet_binding.get_binding", return_value={"address": wallet}
    ), patch(
        "core.historical_bnb_credit_reversal.is_reconciled_invalid_historical_deposit",
        return_value=True,
    ) as valid_compensation:
        result = _audit_historical_bnb_deposits(db, _cfg())

    assert result["ok"] is False
    assert result["reconciled_count"] == 0
    assert result["finding_count"] == 1
    assert "IDEMPOTENCY_KEY_MISMATCH" in result["findings"][0]["issues"]
    valid_compensation.assert_not_called()

def test_historical_invalid_deposit_blocks_opening_evidence_even_with_valid_proof():
    db, empirical, tx_hash, bad_hash, wallet, verified = _historical_deposit_fixture()
    with patch.dict(
        os.environ,
        {
            "BNB_DEPOSITS_OPEN": "0",
            "SLH_BSC_CANONICAL_TREASURY": TREASURY,
        },
        clear=False,
    ), patch("core.bnb_gate._effective_config", return_value=_cfg()), patch(
        "core.bnb_gate._empirical_settlement_evidence", return_value=empirical
    ), patch(
        "core.deposit_monitor.get_onchain_status",
        return_value={
            "ok": True,
            "chain_id": 56,
            "block": 123,
            "treasury_wallet": TREASURY,
            "network": "bsc",
        },
    ), patch(
        "core.deposit_monitor.verify_bnb_deposit",
        side_effect=lambda value: _verify_fixture_tx(value, tx_hash, verified),
    ), patch(
        "core.wallet_binding.get_binding", return_value={"address": wallet}
    ), patch(
        "state_manager.load_db", return_value=db
    ):
        status = bnb_opening_evidence()

    assert status["scope"] == "read_only"
    assert status["historical_deposits"]["status"] == "FAIL"
    assert status["historical_deposits"]["rows_checked"] == 2
    assert status["historical_deposits"]["finding_count"] == 1
    assert status["historical_deposits"]["findings"][0]["tx_suffix"] == bad_hash[-8:]
    assert "CHAIN_TX_NOT_VERIFIED" in status["historical_deposits"]["findings"][0]["issues"]
    assert "HISTORICAL_BNB_DEPOSIT_LEDGER_REVALIDATION_FAILED" in status["blockers"]
    assert status["gate_open"] is False
    assert status["ready_to_open"] is False


def test_public_bnb_gate_fails_closed_on_invalid_historical_deposit():
    from core.bnb_gate import bnb_deposits_open

    db, empirical, tx_hash, bad_hash, wallet, verified = _historical_deposit_fixture()
    with patch.dict(
        os.environ,
        {
            "BNB_DEPOSITS_OPEN": "1",
            "SLH_BSC_CANONICAL_TREASURY": TREASURY,
        },
        clear=False,
    ), patch("core.bnb_gate._effective_config", return_value=_cfg()), patch(
        "core.bnb_gate._empirical_evidence_revalidated", return_value=True
    ), patch(
        "core.deposit_monitor.verify_bnb_deposit",
        side_effect=lambda value: _verify_fixture_tx(value, tx_hash, verified),
    ), patch(
        "core.wallet_binding.get_binding", return_value={"address": wallet}
    ), patch(
        "state_manager.load_db", return_value=db
    ):
        assert bnb_deposits_open() is False




def test_full_historical_audit_accepts_only_real_compensating_entry_with_approval(monkeypatch):
    from core.bnb_gate import _audit_historical_bnb_deposits

    db, empirical, valid_hash, bad_hash, wallet, verified_valid = _historical_deposit_fixture()
    uid = "224223270"
    db["users"] = {uid: {"wallet": {"credits": 18.091775}}}
    correction_key = f"accounting:reversal:{bad_hash.lower()}"
    source_key = f"bnb:deposit:{bad_hash.lower()}"
    correction = {
        "uid": uid,
        "before": 28.091775,
        "amount": -10.0,
        "after": 18.091775,
        "reason": "accounting:invalid_bnb_deposit_reversal",
        "meta": {
            "idempotency_key": correction_key,
            "source_idempotency_key": source_key,
            "source_reason": "bnb:deposit",
            "source_ledger_index": 0,
            "tx_hash": bad_hash.lower(),
            "actor_uid": uid,
            "adjustment_kind": "verified_invalid_nontreasury_bnb_self_transfer",
            "nominal_credits_reversed": 10.0,
            "chain_id": 56,
            "block": 80,
            "confirmations": 21,
            "required_confirmations": 15,
            "amount_wei": 10**16,
            "treasury": TREASURY,
            "from": wallet,
            "to": wallet,
            "source_ledger_rows_preserved": True,
            "later_account_activity_preserved": True,
            "gate_remained_closed": True,
        },
    }
    db["ledger"].append(correction)
    db["credit_adjustment_audit"] = [{
        "event": "INVALID_BNB_NON_TREASURY_SELF_TRANSFER_REVERSED",
        "uid": uid,
        "actor_uid": uid,
        "tx_hash": bad_hash.lower(),
        "source_idempotency_key": source_key,
        "correction_idempotency_key": correction_key,
        "amount": -10.0,
        "nominal_credits_reversed": 10.0,
        "balance_before": 28.091775,
        "balance_after": 18.091775,
        "chain_id": 56,
        "block": 80,
        "confirmations": 21,
        "required_confirmations": 15,
        "gate_remained_closed": True,
    }]
    bad_proof = {
        "tx_hash": bad_hash.lower(),
        "chain_id": 56,
        "receipt_status": 1,
        "from": wallet,
        "to": wallet,
        "treasury": TREASURY,
        "bound_wallet": wallet,
        "amount_wei": 10**16,
        "block": 80,
        "confirmations": 21,
        "required_confirmations": 15,
    }

    def verify_tx(tx):
        if str(tx).lower() == valid_hash.lower():
            return dict(verified_valid)
        return {
            "ok": False,
            "error": "BNB_TX_RECIPIENT_NOT_TREASURY",
            "to": wallet,
            "treasury": TREASURY,
        }

    monkeypatch.setenv("SLH_BSC_CANONICAL_TREASURY", TREASURY)
    monkeypatch.setenv("SLH_BNB_RECONCILED_HISTORY_APPROVED", "1")
    monkeypatch.setattr("core.bnb_gate._effective_config", lambda _db: _cfg())
    monkeypatch.setattr("core.historical_bnb_credit_reversal._effective_config", lambda _db: _cfg())
    monkeypatch.setattr("core.historical_bnb_credit_reversal.is_quarantined_bsc_address", lambda _address: False)
    monkeypatch.setattr(
        "core.historical_bnb_credit_reversal._verify_non_treasury_self_transfer",
        lambda _uid, _tx, _db: dict(bad_proof),
    )
    monkeypatch.setattr("core.deposit_monitor.verify_bnb_deposit", verify_tx)
    monkeypatch.setattr("core.wallet_binding.get_binding", lambda _uid: {"address": wallet})

    result = _audit_historical_bnb_deposits(db, _cfg())

    assert result["ok"] is True
    assert result["rows_checked"] == 2
    assert result["reconciled_count"] == 1
    assert result["finding_count"] == 0
    assert result["findings"] == []

