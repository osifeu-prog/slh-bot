"""Fail-closed invariant for the configured on-chain SLH total supply.

The expected raw total supply must be explicitly provisioned as
SLH_SUPPLY_BASELINE_RAW after an operator verifies the live contract supply.
No guessed/default baseline is used. A missing or invalid baseline blocks
SLH deposit verification rather than risking an internal credit without a
matching, approved supply invariant.
"""

from __future__ import annotations

import os

from web3 import Web3


TOTAL_SUPPLY_ABI = [
    {
        "constant": True,
        "inputs": [],
        "name": "totalSupply",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function",
    }
]


def _configured_baseline(baseline_raw=None) -> int:
    if baseline_raw is None:
        if "SLH_SUPPLY_BASELINE_RAW" not in os.environ:
            raise ValueError("SLH_SUPPLY_BASELINE_NOT_CONFIGURED")
        raw = os.environ.get("SLH_SUPPLY_BASELINE_RAW", "")
    else:
        raw = baseline_raw

    try:
        baseline = int(str(raw).strip())
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("SLH_SUPPLY_BASELINE_INVALID") from exc

    if baseline <= 0:
        raise ValueError("SLH_SUPPLY_BASELINE_INVALID")
    return baseline


def assert_supply_unchanged(web3, token_address, *, baseline_raw=None) -> dict:
    """Require live totalSupply() to exactly match an operator-set raw baseline.

    Raises stable ValueError codes so callers can fail closed without exposing
    RPC internals. The raw integer is used to avoid decimal/float rounding.
    """
    baseline = _configured_baseline(baseline_raw)

    try:
        address = Web3.to_checksum_address(str(token_address))
        contract = web3.eth.contract(address=address, abi=TOTAL_SUPPLY_ABI)
        current = int(contract.functions.totalSupply().call())
    except Exception as exc:
        raise ValueError("SLH_SUPPLY_UNAVAILABLE") from exc

    if current <= 0:
        raise ValueError("SLH_SUPPLY_UNAVAILABLE")
    if current != baseline:
        raise ValueError("SLH_SUPPLY_MISMATCH")

    return {
        "ok": True,
        "token_contract": address,
        "total_supply_raw": current,
        "baseline_raw": baseline,
    }
