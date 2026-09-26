"""Server-side Telegram Stars invoice authority for the Mini App.

The Mini App supplies only a purchase kind and identifier. Prices and payment
payloads are resolved here from the existing SLH authorities. Fulfillment stays
in the existing successful_payment handlers and is never performed by this
endpoint.
"""

import os
import re

import requests

from core.stars_price_authority import (
    CREDIT_PACKS,
    TELEGRAM_STARS_CURRENCY,
    VIP_MONTHLY_STARS,
    VIP_SUBSCRIPTION_PERIOD,
)

_ITEM_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def build_invoice_request(uid, kind, item_id):
    uid = str(uid or "").strip()
    kind = str(kind or "").strip()
    item_id = str(item_id or "").strip()

    if not uid.isdigit():
        raise ValueError("INVALID_UID")

    if kind == "credit_pack":
        try:
            stars = int(item_id)
        except (TypeError, ValueError):
            raise ValueError("UNKNOWN_PACK")
        pack = next((p for p in CREDIT_PACKS if int(p.stars) == stars), None)
        if pack is None:
            raise ValueError("UNKNOWN_PACK")
        return {
            "title": f"{int(pack.credits)} Credits",
            "description": f"SLH OS · {int(pack.credits)} Credits ({int(pack.stars)} Stars)",
            "payload": f"credits_{int(pack.credits)}_{uid}",
            "stars": int(pack.stars),
        }

    if kind == "store_item":
        if not _ITEM_ID_RE.fullmatch(item_id):
            raise ValueError("UNKNOWN_ITEM")
        from store.stars_purchase_service import get_stars_price
        price = get_stars_price(item_id)
        if price is None:
            raise ValueError("UNKNOWN_ITEM")
        return {
            "title": f"SLH Store · {item_id}"[:32],
            "description": f"SLH OS Store item {item_id} ({int(price)} Stars)",
            "payload": f"item_{item_id}_{uid}",
            "stars": int(price),
        }

    if kind == "vip_monthly":
        if item_id != "vip_monthly":
            raise ValueError("UNKNOWN_ITEM")
        return {
            "title": "SLH VIP",
            "description": "SLH VIP · 499 Stars לחודש.",
            "payload": f"vip_monthly_{uid}",
            "stars": int(VIP_MONTHLY_STARS),
            "recurring": True,
        }

    raise ValueError("UNKNOWN_KIND")


def create_invoice_link(req):
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN_MISSING")

    body = {
        "title": str(req["title"])[:32],
        "description": str(req["description"])[:255],
        "payload": str(req["payload"]),
        "currency": TELEGRAM_STARS_CURRENCY,
        "prices": [{"label": str(req["title"])[:32], "amount": int(req["stars"])}],
    }
    if req.get("recurring"):
        body["subscription_period"] = int(VIP_SUBSCRIPTION_PERIOD)

    response = requests.post(
        f"https://api.telegram.org/bot{token}/createInvoiceLink",
        json=body,
        timeout=15,
    )
    data = response.json()
    if not data.get("ok") or not data.get("result"):
        raise RuntimeError("TELEGRAM_INVOICE_FAILED")
    return str(data["result"])
