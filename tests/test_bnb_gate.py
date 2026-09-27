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


def test_bnb_readiness_uses_state_db_override(tmp_path):
    import json
    from unittest.mock import patch

    db_path = tmp_path / "state" / "db.json"
    db_path.parent.mkdir()
    db_path.write_text(json.dumps({
        "bsc_settings": {
            "treasury_wallet": "0x1111111111111111111111111111111111111111",
            "confirmations": 20,
        }
    }), encoding="utf-8")
    base = {
        "network": "bsc",
        "rpc": "https://example.invalid",
        "chain_id": 56,
        "confirmations": 15,
    }
    with patch.dict(os.environ, {"BNB_DEPOSITS_OPEN": "1"}, clear=False), patch(
        "core.bnb_gate.get_bsc_config", return_value=base
    ), patch("core.bnb_gate.Path", return_value=db_path):
        status = bnb_readiness()
        assert status["ready"] is True
        assert status["confirmations_required"] == 20
        assert status["effective_open"] is True
