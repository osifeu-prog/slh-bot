"""Fail-closed gate for SLH OS-managed user-signed external BSC transfers.

This gate controls only app-prepared transactions. It cannot block a transaction
a user creates and signs independently in their own wallet, and it does not
block verification/settlement of transactions already broadcast by a wallet.
"""
import os


ENV_NAME = "SLH_BSC_USER_SIGNED_TRANSFERS_OPEN"


def user_signed_transfers_open() -> bool:
    return os.getenv(ENV_NAME, "0").strip() == "1"


def require_user_signed_transfers_open() -> None:
    if not user_signed_transfers_open():
        raise ValueError("BSC_USER_SIGNED_TRANSFERS_CLOSED")
