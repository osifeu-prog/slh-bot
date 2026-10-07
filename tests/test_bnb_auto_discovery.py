from unittest.mock import patch

from core import bnb_auto_discovery


UID = "8789977826"
SENDER = "0x1111111111111111111111111111111111111111"
TREASURY = "0x2222222222222222222222222222222222222222"
TX = "0x" + "ab" * 32


def _cfg():
    return {
        "rpc": "https://example.invalid",
        "chain_id": 56,
        "treasury_wallet": TREASURY,
    }


class FakeEth:
    chain_id = 56


class FakeWeb3:
    HTTPProvider = staticmethod(lambda _rpc: _rpc)

    def __init__(self, _provider):
        self.eth = FakeEth()

    @staticmethod
    def to_checksum_address(value):
        return value


def test_discovery_finds_exact_native_bnb_transfer():
    payload = [{
        "hash": TX,
        "timestamp": 1791370800,
        "from": SENDER,
        "to": TREASURY,
        "rawValue": str(10**16),
        "success": True,
    }]
    with patch.object(bnb_auto_discovery, "get_binding", return_value={"address": SENDER}),          patch.object(bnb_auto_discovery, "_config", return_value=_cfg()),          patch.object(bnb_auto_discovery, "Web3", FakeWeb3),          patch.object(
             bnb_auto_discovery.requests,
             "get",
             return_value=type("R", (), {
                 "raise_for_status": lambda self: None,
                 "json": lambda self: payload,
             })(),
         ),          patch.object(
             bnb_auto_discovery,
             "_ledger_keys",
             return_value=set(),
         ):
        result = bnb_auto_discovery.discover_bnb_transfer(UID)

    assert result["status"] == "FOUND"
    assert result["candidate"]["tx_hash"] == TX
    assert result["candidate"]["amount_wei"] == 10**16


def test_discovery_is_fail_closed_on_multiple_unsettled_matches():
    payload = [
        {
            "hash": TX,
            "timestamp": 1791370800,
            "from": SENDER,
            "to": TREASURY,
            "rawValue": str(10**16),
            "success": True,
        },
        {
            "hash": "0x" + "cd" * 32,
            "timestamp": 1791370700,
            "from": SENDER,
            "to": TREASURY,
            "rawValue": str(10**16),
            "success": True,
        },
    ]
    with patch.object(bnb_auto_discovery, "get_binding", return_value={"address": SENDER}),          patch.object(bnb_auto_discovery, "_config", return_value=_cfg()),          patch.object(bnb_auto_discovery, "Web3", FakeWeb3),          patch.object(
             bnb_auto_discovery.requests,
             "get",
             return_value=type("R", (), {
                 "raise_for_status": lambda self: None,
                 "json": lambda self: payload,
             })(),
         ),          patch.object(
             bnb_auto_discovery,
             "_ledger_keys",
             return_value=set(),
         ):
        result = bnb_auto_discovery.discover_bnb_transfer(UID)

    assert result["status"] == "AMBIGUOUS"
    assert len(result["candidates"]) == 2


def test_discovery_ignores_wrong_amount_and_wrong_recipient():
    payload = [
        {
            "hash": TX,
            "timestamp": 1791370800,
            "from": SENDER,
            "to": TREASURY,
            "rawValue": str(10**15),
            "success": True,
        },
        {
            "hash": "0x" + "ef" * 32,
            "timestamp": 1791370700,
            "from": SENDER,
            "to": "0x3333333333333333333333333333333333333333",
            "rawValue": str(10**16),
            "success": True,
        },
    ]
    with patch.object(bnb_auto_discovery, "get_binding", return_value={"address": SENDER}),          patch.object(bnb_auto_discovery, "_config", return_value=_cfg()),          patch.object(bnb_auto_discovery, "Web3", FakeWeb3),          patch.object(
             bnb_auto_discovery.requests,
             "get",
             return_value=type("R", (), {
                 "raise_for_status": lambda self: None,
                 "json": lambda self: payload,
             })(),
         ),          patch.object(
             bnb_auto_discovery,
             "_ledger_keys",
             return_value=set(),
         ), patch.object(
             bnb_auto_discovery,
             "_latest_handoff_timestamp",
             return_value=None,
         ):
        result = bnb_auto_discovery.discover_bnb_transfer(UID)

    assert result["status"] == "NOT_FOUND"


def test_discovery_falls_back_to_bsc_rpc_handoff_window():
    candidate = {
        "tx_hash": TX,
        "timestamp": 1791370800,
        "block": 123456,
        "amount_wei": 10**16,
        "from": SENDER,
        "to": TREASURY,
    }
    with patch.object(bnb_auto_discovery, "get_binding", return_value={"address": SENDER}), \
         patch.object(bnb_auto_discovery, "_config", return_value=_cfg()), \
         patch.object(bnb_auto_discovery, "Web3", FakeWeb3), \
         patch.object(
             bnb_auto_discovery.requests,
             "get",
             return_value=type("R", (), {
                 "raise_for_status": lambda self: None,
                 "json": lambda self: [],
             })(),
         ), \
         patch.object(bnb_auto_discovery, "_ledger_keys", return_value=set()), \
         patch.object(
             bnb_auto_discovery,
             "_latest_handoff_timestamp",
             return_value=1791370800,
         ), \
         patch.object(
             bnb_auto_discovery,
             "_rpc_find_exact_transfers",
             return_value=[candidate],
         ):
        result = bnb_auto_discovery.discover_bnb_transfer(UID)

    assert result["status"] == "FOUND"
    assert result["provider"] == "BSC_RPC_HANDOFF_WINDOW"
    assert result["candidate"]["tx_hash"] == TX
    assert result["candidate"]["block"] == 123456
