import pytest

from core import bnb_quick_return


def test_bnb_return_config_is_owner_only(monkeypatch):
    monkeypatch.setattr(
        bnb_quick_return,
        "get_binding",
        lambda uid: {"address": (
            "0x1111111111111111111111111111111111111111"
            if str(uid) == "8789977826"
            else "0x2222222222222222222222222222222222222222"
        )},
    )
    monkeypatch.setattr(
        bnb_quick_return,
        "_bsc_config",
        lambda: {"rpc": "https://bsc-dataseed.bnbchain.org", "chain_id": 56},
    )

    with pytest.raises(PermissionError, match="OWNER_ONLY"):
        bnb_quick_return.get_bnb_return_config("123")

    result = bnb_quick_return.get_bnb_return_config("8789977826")
    assert result["amount_bnb"] == "0.01"
    assert result["amount_wei"] == "10000000000000000"
    repay = bnb_quick_return.get_bnb_return_config("8789977826", preset="repay_1")
    assert repay["amount_bnb"] == "1"
    assert repay["amount_wei"] == "1000000000000000000"
    assert repay["purpose"] == "BNB_REPAYMENT"
    assert result["chain_id"] == 56
    assert result["recipient"] == "0x2222222222222222222222222222222222222222"
    assert result["server_broadcast"] is False
    assert result["custody"] is False


def test_bnb_return_config_rejects_self_transfer(monkeypatch):
    monkeypatch.setattr(
        bnb_quick_return,
        "get_binding",
        lambda uid: {"address": "0x1111111111111111111111111111111111111111"},
    )
    monkeypatch.setattr(
        bnb_quick_return,
        "_bsc_config",
        lambda: {"rpc": "https://bsc-dataseed.bnbchain.org", "chain_id": 56},
    )
    with pytest.raises(ValueError, match="BNB_RETURN_SELF_TRANSFER_BLOCKED"):
        bnb_quick_return.get_bnb_return_config("8789977826")
