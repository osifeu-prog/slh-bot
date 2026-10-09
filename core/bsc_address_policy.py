"""Fail-closed policy for owner-reported compromised BSC addresses.

ZUZ is a forensic alias only. It is not a BEP-20 contract, transferable asset,
or internal wallet balance. This module deliberately preserves read-only
forensic classification while prohibiting operational use.
"""
from __future__ import annotations

from typing import Any

OWNER_TREZOR_ADDRESS = "0x468328B2a7C9b5629e87844Bb4531e7409400b34"

QUARANTINED_BSC_ADDRESSES: dict[str, dict[str, Any]] = {
    "0x693db6c817083818696a7228aebfbd0cd3371f02": {
        "forensic_alias": "ZUZ",
        "classification": "owner_reported_compromised",
        "status": "QUARANTINED",
        "operational_use_allowed": False,
        "forensic_read_only": True,
    }
}


def _key(address: Any) -> str:
    return str(address or "").strip().lower()


def is_quarantined_bsc_address(address: Any) -> bool:
    """Whether an address is explicitly quarantined for BSC operations."""
    return _key(address) in QUARANTINED_BSC_ADDRESSES


def forensic_alias(address: Any) -> str | None:
    """Return a read-only forensic label for a quarantined address."""
    record = QUARANTINED_BSC_ADDRESSES.get(_key(address))
    return str(record["forensic_alias"]) if record else None


def forensic_record(address: Any) -> dict[str, Any] | None:
    """Return classification metadata without creating a wallet or balance."""
    record = QUARANTINED_BSC_ADDRESSES.get(_key(address))
    if not record:
        return None
    return {"address": str(address).strip(), **record, "scope": "BSC"}


def require_usable_bsc_address(address: Any, *, role: str = "address") -> str:
    """Raise before operational use of a quarantined address."""
    if is_quarantined_bsc_address(address):
        raise ValueError("BSC_ADDRESS_QUARANTINED_ZUZ")
    return str(address or "").strip()
