import os
from unittest.mock import patch

from core.bnb_gate import bnb_deposits_open, bnb_readiness


def test_bnb_gate_is_closed_without_treasury():
    with patch.dict(os.environ, {"BNB_DEPOSITS_OPEN": "1"}, clear=False), patch(
        "core.bnb_gate.get_bsc_config",
        return_value={"network": "bsc", "rpc": "https://example.invalid", "chain_id": 56, "confirmations": 15},
    ):
        status = bnb_readiness()
        assert status["flag_open"] is True
        assert status["effective_open"] is False
        assert "BNB_TREASURY_MISSING" in status["reasons"]
        assert bnb_deposits_open() is False


def test_bnb_gate_opens_only_when_flag_and_config_are_ready():
    with patch.dict(os.environ, {"BNB_DEPOSITS_OPEN": "1"}, clear=False), patch(
        "core.bnb_gate.get_bsc_config",
        return_value={
            "network": "bsc",
            "rpc": "https://example.invalid",
            "chain_id": 56,
            "confirmations": 15,
            "treasury_wallet": "0x1111111111111111111111111111111111111111",
        },
    ):
        status = bnb_readiness()
        assert status["ready"] is True
        assert status["effective_open"] is True
        assert bnb_deposits_open() is True
