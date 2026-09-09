"""Canonical internal-credit mint authority for Sela AIR.

Minting means creating new internal credits.  It is intentionally distinct
from P2P transfers, staking, and payment settlement.

At the current Alpha stage only the canonical OWNER may invoke this authority.
Handlers must not implement their own mint permission checks or write directly
to the wallet for mint operations.
"""

from core.authority import require_owner, normalize_uid
from core import economy_service


MINT_PERMISSION = "economy.mint"


def mint_credits(issuer_uid, recipient_uid, amount, reason="mint", meta=None):
    """Create new internal credits, OWNER only.

    Returns the recipient's resulting credit balance.
    """
    issuer_uid = normalize_uid(issuer_uid)
    recipient_uid = normalize_uid(recipient_uid)

    if not require_owner(issuer_uid):
        raise PermissionError("OWNER_ONLY_MINT")

    if not isinstance(amount, (int, float)):
        raise TypeError("amount must be numeric")

    if amount <= 0:
        raise ValueError("MINT_AMOUNT_MUST_BE_POSITIVE")

    metadata = dict(meta or {})
    metadata.update({
        "source": "mint_authority",
        "issuer_uid": issuer_uid,
        "permission": MINT_PERMISSION,
    })

    return economy_service.record_transaction(
        recipient_uid,
        amount,
        reason=reason,
        meta=metadata,
    )
