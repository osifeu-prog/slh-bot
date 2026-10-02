"""Signing boundary for BSC execution.

Private keys are intentionally not stored in this repository, state/db.json, or
inside core.bsc_execution. A production signer should live behind an HSM/KMS
or dedicated external custody boundary and return only signed transaction bytes.
"""
from __future__ import annotations

from typing import Any, Mapping, Protocol


class BSCTransactionSigner(Protocol):
    def address(self) -> str:
        """Return the public EVM address controlled by the signer."""

    def sign_transaction(self, transaction: Mapping[str, Any]) -> str:
        """Return a 0x-prefixed raw signed transaction."""
