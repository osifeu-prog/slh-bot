from unittest.mock import patch

import pytest

from core import slh_quick_send


def _binding(uid, address):
    return {"uid": str(uid), "chain": "bsc", "chain_id": 56, "address": address}


def test_owner_quick_send_resolves_live_recipient_binding():
    owner = "8789977826"
    owner_address = "0x1111111111111111111111111111111111111111"
    tzvika_address = "0x2222222222222222222222222222222222222222"
    with patch.object(slh_quick_send, "get_binding", side_effect=lambda uid: (
        _binding(owner, owner_address)
        if str(uid) == owner
        else _binding("5010371391", tzvika_address)
    )), patch.object(
        slh_quick_send, "_bsc_config", return_value={"token_contract": "0xACb0A09414CEA1C879c67bB7A877E4e19480f022"}
    ):
        result = slh_quick_send.get_quick_send_config(owner, "owner_to_tzvika_1")

    assert result["recipient"] == tzvika_address
    assert result["sender"] == owner_address
    assert result["amount_slh"] == "1"
    assert result["chain_id"] == 56
    assert result["signing"] == "user_wallet_only"
    assert result["custody"] is False


def test_quick_send_is_owner_only():
    with pytest.raises(PermissionError, match="OWNER_ONLY"):
        slh_quick_send.get_quick_send_config("5010371391", "owner_to_tzvika_1")


def test_quick_send_rejects_missing_recipient_binding():
    owner = "8789977826"
    with patch.object(slh_quick_send, "get_binding", side_effect=lambda uid: (
        _binding(owner, "0x1111111111111111111111111111111111111111")
        if str(uid) == owner
        else None
    )):
        with pytest.raises(ValueError, match="RECIPIENT_BSC_WALLET_NOT_VERIFIED"):
            slh_quick_send.get_quick_send_config(owner, "owner_to_tzvika_1")
