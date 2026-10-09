import os
from unittest.mock import patch

from core.bnb_gate import bnb_deposits_open, bnb_readiness


TREASURY = "0x1111111111111111111111111111111111111111"


def _cfg(treasury=TREASURY):
    return {
        "network": "bsc",
        "rpc": "https://example.invalid",
        "chain_id": 56,
        "confirmations": 15,
        "treasury_wallet": treasury,
    }


def test_bnb_gate_is_closed_without_treasury():
    with patch.dict(
        os.environ,
        {
            "BNB_DEPOSITS_OPEN": "1",
            "SLH_BSC_CANONICAL_TREASURY": TREASURY,
        },
        clear=False,
    ), patch(
        "core.bnb_gate._effective_config",
        return_value={**_cfg(), "treasury_wallet": ""},
    ):
        status = bnb_readiness()
        assert status["flag_open"] is True
        assert status["effective_open"] is False
        assert "BNB_TREASURY_MISSING" in status["reasons"]
        assert bnb_deposits_open() is False


def test_bnb_gate_stays_closed_without_explicit_canonical_treasury():
    with patch.dict(os.environ, {"BNB_DEPOSITS_OPEN": "1"}, clear=False), patch(
        "core.bnb_gate._effective_config",
        return_value=_cfg(),
    ):
        status = bnb_readiness()
        assert status["ready"] is False
        assert status["effective_open"] is False
        assert "BNB_CANONICAL_TREASURY_MISSING" in status["reasons"]


def test_bnb_gate_opens_only_with_flag_config_and_revalidated_empirical_proof():
    with patch.dict(
        os.environ,
        {
            "BNB_DEPOSITS_OPEN": "1",
            "SLH_BSC_CANONICAL_TREASURY": TREASURY,
        },
        clear=False,
    ), patch(
        "core.bnb_gate._effective_config",
        return_value=_cfg(),
    ), patch(
        "core.bnb_gate._empirical_settlement_evidence",
        return_value={"status": "PASS", "tx_hash": "fixture"},
    ), patch(
        "core.bnb_gate._empirical_evidence_revalidated",
        return_value=True,
    ):
        status = bnb_readiness()
        assert status["ready"] is True
        assert status["effective_open"] is True
        assert bnb_deposits_open() is True


def test_bnb_gate_stays_closed_when_empirical_proof_is_missing_even_if_flag_and_config_match():
    with patch.dict(
        os.environ,
        {
            "BNB_DEPOSITS_OPEN": "1",
            "BNB_DEPOSITS_CANARY_UID": "",
            "SLH_BSC_CANONICAL_TREASURY": TREASURY,
        },
        clear=False,
    ), patch(
        "core.bnb_gate._effective_config",
        return_value=_cfg(),
    ), patch(
        "core.bnb_gate._empirical_settlement_evidence",
        return_value=None,
    ):
        status = bnb_readiness()
        assert status["ready"] is True
        assert status["effective_open"] is True
        assert bnb_deposits_open() is False


def test_bnb_gate_closes_on_canonical_treasury_mismatch():
    with patch.dict(
        os.environ,
        {
            "BNB_DEPOSITS_OPEN": "1",
            "SLH_BSC_CANONICAL_TREASURY": "0x2222222222222222222222222222222222222222",
        },
        clear=False,
    ), patch(
        "core.bnb_gate._effective_config",
        return_value=_cfg(),
    ):
        status = bnb_readiness()
        assert status["ready"] is False
        assert status["effective_open"] is False
        assert "BNB_CANONICAL_TREASURY_MISMATCH" in status["reasons"]


def test_bnb_readiness_uses_state_db_override():
    base = {
        "network": "bsc",
        "rpc": "https://example.invalid",
        "chain_id": 56,
        "confirmations": 15,
    }
    with patch.dict(
        os.environ,
        {
            "BNB_DEPOSITS_OPEN": "1",
            "SLH_BSC_CANONICAL_TREASURY": TREASURY,
        },
        clear=False,
    ), patch("core.bnb_gate.get_bsc_config", return_value=base), patch(
        "core.bnb_gate.state_manager.load_db",
        return_value={
            "bsc_settings": {
                "treasury_wallet": TREASURY,
                "confirmations": 20,
            }
        },
    ):
        status = bnb_readiness()
        assert status["ready"] is True
        assert status["confirmations_required"] == 20
        assert status["effective_open"] is True
