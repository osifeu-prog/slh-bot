from unittest import mock

from core import bsc_wallet_read_model


def test_unverified_wallet_never_reads_chain():
    with mock.patch.object(bsc_wallet_read_model, "get_binding", return_value=None),          mock.patch.object(bsc_wallet_read_model, "Web3") as web3:
        result = bsc_wallet_read_model.read_bsc_wallet("123")
    assert result["ok"] is False
    assert result["reason"] == "BNB_WALLET_NOT_VERIFIED"
    web3.assert_not_called()


def test_wallet_read_model_contract_is_read_only():
    source = open("core/bsc_wallet_read_model.py", encoding="utf-8").read()
    assert "eth.send" not in source
    assert "atomic_update" not in source
    assert "read_only" in source
