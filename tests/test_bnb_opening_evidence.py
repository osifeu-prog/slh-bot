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
