import os
from unittest.mock import patch

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
        return_value={"ok": False, "error": "rpc unavailable"},
    ):
        status = bnb_opening_evidence()

    assert status["status"] == "BLOCKED"
    assert status["ready_to_open"] is False
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
        "ledger": [{
            "uid": "224223270",
            "reason": "bnb:deposit",
            "amount": 10.0,
            "before": 100.0,
            "after": 110.0,
            "meta": {"idempotency_key": f"bnb:deposit:{tx_hash.lower()}"},
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

    live_tx_check.assert_called_once_with(tx_hash)
    binding_lookup.assert_called_once_with("224223270")
    ledger_load.assert_called_once_with()
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
    ):
        status = bnb_opening_evidence()

    assert status["live_rpc"]["status"] == "NOT_CHECKED"
    assert "LIVE_BSC_RPC_UNVERIFIED" not in status["blockers"]
    assert "BNB_TREASURY_QUARANTINED_ZUZ" in status["blockers"]
    assert status["ready_to_open"] is False
    assert status["status"] == "BLOCKED"
