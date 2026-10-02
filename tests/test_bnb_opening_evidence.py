import os
from unittest.mock import patch

from core.bnb_gate import bnb_opening_evidence


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



from unittest.mock import patch


def test_record_bnb_empirical_reconciliation_requires_exact_ledger_and_binding(monkeypatch):
    from core.bnb_gate import record_bnb_empirical_reconciliation

    uid = "8789977826"
    tx_hash = "0x" + "ab" * 32
    sender = "0x2222222222222222222222222222222222222222"
    treasury = TREASURY
    ledger = [
        {
            "uid": uid,
            "amount": 1.0,
            "reason": "bnb:deposit",
            "meta": {
                "idempotency_key": f"bnb:deposit:{tx_hash}",
                "tx_hash": tx_hash,
            },
        }
    ]
    db = {"users": {uid: {"wallet": {"credits": 1.0}}}, "ledger": ledger}

    monkeypatch.setenv("SLH_BSC_CANONICAL_TREASURY", treasury)

    def fake_atomic_update(mutate):
        return mutate(db)

    with patch("core.wallet_binding.get_binding", return_value={
        "uid": uid,
        "chain": "bsc",
        "address": sender,
        "verified_at": "2026-10-02T12:50:00Z",
    }), patch("core.deposit_monitor.verify_bnb_deposit", return_value={
        "ok": True,
        "from": sender,
        "to": treasury,
        "amount_wei": 10**15,
        "amount_bnb": 0.001,
        "block": 123,
        "confirmations": 15,
        "required_confirmations": 15,
    }), patch("state_manager.load_db", return_value=db),          patch("state_manager.atomic_update", side_effect=fake_atomic_update):
        result = record_bnb_empirical_reconciliation(uid, tx_hash)

    assert result["status"] == "PASS"
    assert result["uid"] == uid
    assert result["tx_hash"] == tx_hash
    assert result["credits"] == "1.0"
    assert result["idempotent"] is False
    assert db["bnb_empirical_reconciliations"][tx_hash]["status"] == "PASS"


def test_bnb_opening_evidence_turns_ready_after_empirical_pass():
    with patch.dict(
        os.environ,
        {
            "BNB_DEPOSITS_OPEN": "0",
            "SLH_BSC_CANONICAL_TREASURY": TREASURY,
        },
        clear=False,
    ), patch("core.bnb_gate._effective_config", return_value=_cfg()), patch(
        "core.bnb_gate._effective_db",
        return_value={
            "bnb_empirical_reconciliations": {
                "0x" + "cd" * 32: {
                    "status": "PASS",
                    "schema_version": 1,
                    "uid": "8789977826",
                    "tx_hash": "0x" + "cd" * 32,
                    "chain_id": 56,
                    "treasury": TREASURY.lower(),
                    "sender": "0x2222222222222222222222222222222222222222",
                    "amount_wei": 10**15,
                    "amount_bnb": "0.001",
                    "credits": "1.0",
                    "confirmations": 15,
                    "required_confirmations": 15,
                    "ledger_entries": 1,
                    "idempotency_key": "bnb:deposit:" + "0x" + "cd" * 32,
                    "deployment_commit": "test",
                }
            }
        },
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

    assert status["status"] == "READY_TO_OPEN"
    assert status["ready_to_open"] is True
    assert status["gate_open"] is False
    assert status["checks"]["wallet_binding"]["status"] == "PASS"
    assert status["checks"]["tx_verification"]["status"] == "PASS"
    assert status["checks"]["idempotency"]["status"] == "PASS"
    assert status["checks"]["atomic_ledger"]["status"] == "PASS"
    assert status["checks"]["reconciliation"]["status"] == "PASS"
