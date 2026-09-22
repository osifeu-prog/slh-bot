"""Canonical Telegram Stars pricing for the SLH economy.

Stars are the external pricing authority. Internal Credits and entitlements
must be derived from these definitions rather than duplicating price literals.
"""

from dataclasses import dataclass


TELEGRAM_STARS_CURRENCY = "XTR"
VIP_MONTHLY_STARS = 499
VIP_SUBSCRIPTION_PERIOD = 2592000


@dataclass(frozen=True)
class CreditPack:
    pack_id: str
    stars: int
    credits: int
    label: str

    @property
    def button_text(self) -> str:
        return f"⭐ {self.stars} Stars → {self.credits} Credits ({self.label})"


CREDIT_PACKS = (
    CreditPack("100credits", 100, 100, "בסיס"),
    CreditPack("500credits", 500, 550, "בונוס 10%"),
    CreditPack("1000credits", 1000, 1200, "בונוס 20%"),
)

CREDIT_PACKS_BY_ID = {pack.pack_id: pack for pack in CREDIT_PACKS}


def resolve_credit_pack(credits: int, stars_paid: int) -> CreditPack | None:
    try:
        credits = int(credits)
        stars_paid = int(stars_paid)
    except (TypeError, ValueError):
        return None

    for pack in CREDIT_PACKS:
        if pack.credits == credits and pack.stars == stars_paid:
            return pack
    return None
