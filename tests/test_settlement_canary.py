import os
from unittest.mock import patch

from core.bnb_gate import bnb_settlement_allowed
from core import ton_deposit_service


def test_bnb_canary_does_not_open_gate_but_allows_owner_settlement():
    db = {}
    with patch.dict(os.environ, {
        "BNB_DEPOSITS_OPEN": "0",
        "BNB_DEPOSITS_CANARY_UID": "8789977826",
        "SLH_BSC_CANONICAL_TREASURY": "0x1111111111111111111111111111111111111111",
    }, clear=False), patch(
        "core.bnb_gate.bnb_readiness",
        return_value={"ready": True, "effective_open": False},
    ), patch(
        "core.bnb_gate.bnb_deposits_open",
        return_value=False,
    ):
        assert bnb_settlement_allowed("8789977826", db) is True
        assert bnb_settlement_allowed("5010371391", db) is False


def test_ton_canary_allows_explicit_settlement_when_closed():
    with patch.dict(os.environ, {
        "TON_DEPOSITS_OPEN": "0",
        "TON_DEPOSITS_CANARY_UID": "8789977826",
    }, clear=False), patch.object(
        ton_deposit_service,
        "ton_readiness",
        return_value={"ready": True, "effective_open": False},
    ):
        assert ton_deposit_service.ton_settlement_allowed("8789977826") is True
        assert ton_deposit_service.ton_settlement_allowed("5010371391") is False


def test_ton_canary_never_overrides_unsafe_readiness():
    with patch.dict(os.environ, {
        "TON_DEPOSITS_OPEN": "0",
        "TON_DEPOSITS_CANARY_UID": "8789977826",
    }, clear=False), patch.object(
        ton_deposit_service,
        "ton_readiness",
        return_value={"ready": False, "effective_open": False},
    ):
        assert ton_deposit_service.ton_settlement_allowed("8789977826") is False
