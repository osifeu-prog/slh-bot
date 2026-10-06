"""Canonical owner Quick Send presets for user-signed SLH transfers.

Presets are read-only UX configuration. The recipient address is always
resolved from the recipient's current verified BSC wallet binding, never
stored as a hard-coded wallet address.
"""

from __future__ import annotations

from typing import Any

from core.distribution_wallet_registry import _bsc_config
from core.identity import OWNER_TELEGRAM_ID
from core.wallet_binding import get_binding


QUICK_SEND_PRESETS: dict[str, dict[str, str]] = {
    "owner_to_tzvika_1": {
        "recipient_uid": "5010371391",
        "label": "צביקה",
        "amount_slh": "1",
    },
}


def get_quick_send_config(uid: Any, preset: Any) -> dict[str, Any]:
    """Return a server-resolved, read-only Quick Send preset for the owner."""
    uid = str(uid or "").strip()
    preset = str(preset or "").strip()
    if uid != str(OWNER_TELEGRAM_ID):
        raise PermissionError("OWNER_ONLY")

    config = QUICK_SEND_PRESETS.get(preset)
    if not config:
        raise ValueError("QUICK_SEND_PRESET_NOT_FOUND")

    recipient_uid = str(config["recipient_uid"])
    recipient_binding = get_binding(recipient_uid)
    if not recipient_binding:
        raise ValueError("RECIPIENT_BSC_WALLET_NOT_VERIFIED")

    recipient = str(recipient_binding.get("address") or "").strip()
    if not recipient:
        raise ValueError("RECIPIENT_BSC_WALLET_NOT_VERIFIED")

    sender_binding = get_binding(uid)
    sender = str(sender_binding.get("address") or "").strip() if sender_binding else ""
    if not sender:
        raise ValueError("OWNER_BSC_WALLET_NOT_VERIFIED")

    if sender.lower() == recipient.lower():
        raise ValueError("QUICK_SEND_SELF_TRANSFER_BLOCKED")

    bsc = _bsc_config()
    token = str(bsc.get("token_contract") or "").strip()
    if not token:
        raise ValueError("SLH_TOKEN_CONTRACT_NOT_CONFIGURED")

    return {
        "ok": True,
        "preset": preset,
        "label": config["label"],
        "sender_uid": uid,
        "sender": sender,
        "recipient_uid": recipient_uid,
        "recipient": recipient,
        "amount_slh": config["amount_slh"],
        "chain_id": 56,
        "token_contract": token,
        "signing": "user_wallet_only",
        "custody": False,
    }
