"""Canonical monetization-path status for the SLH Control Plane.

This module reports implementation status, not financial totals. It deliberately
does not infer cash revenue from internal Credits or exchange activity.
"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _exists(relative: str) -> bool:
    return (ROOT / relative).is_file()


def _stars_store_items() -> list[dict]:
    path = ROOT / "store" / "items.json"
    try:
        items = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    rows = []
    for item_id, item in items.items():
        if not isinstance(item, dict):
            continue
        try:
            stars = int(item.get("price_stars", 0) or 0)
        except (TypeError, ValueError):
            stars = 0
        if stars > 0:
            rows.append(
                {
                    "item_id": str(item_id),
                    "price_stars": stars,
                    "name": str(item.get("name", item_id)),
                }
            )
    return rows


def income_paths() -> list[dict]:
    stars_items = _stars_store_items()
    return [
        {
            "id": "telegram_stars_credits",
            "kind": "external_payment",
            "status": "implemented_automated",
            "currency": "XTR",
            "source": "handlers/payment_handler.py",
            "authority": "core/stars_payment_authority.py",
            "evidence": _exists("handlers/payment_handler.py")
            and _exists("core/stars_payment_authority.py"),
        },
        {
            "id": "telegram_stars_store",
            "kind": "external_payment",
            "status": "implemented_automated" if stars_items else "not_configured",
            "currency": "XTR",
            "source": "store/stars_purchase_service.py",
            "authority": "store/stars_purchase_service.py",
            "items": stars_items,
            "evidence": _exists("store/stars_purchase_service.py") and bool(stars_items),
        },
        {
            "id": "manual_shop_ils_ton",
            "kind": "external_payment",
            "status": "manual_unclosed",
            "currency": "ILS/TON",
            "source": "handlers/shop_handler.py",
            "notes": "Order creation and payment claim exist; automated payment verification and fulfillment settlement are not the production authority.",
            "evidence": _exists("handlers/shop_handler.py"),
        },
        {
            "id": "bnb_deposit_to_credits",
            "kind": "external_deposit",
            "status": "implemented_verified_binding",
            "currency": "BNB",
            "source": "handlers/claim_handler.py",
            "authority": "core/bnb_deposit_service.py",
            "evidence": _exists("handlers/claim_handler.py") and _exists("core/bnb_deposit_service.py"),
        },
        {
            "id": "ton_deposit_to_credits",
            "kind": "external_deposit",
            "status": "paused",
            "currency": "TON",
            "source": "core/economy_service.py",
            "notes": "Automated TON crediting remains intentionally paused pending verified user binding.",
            "evidence": _exists("core/economy_service.py"),
        },
        {
            "id": "withdrawal",
            "kind": "payout",
            "status": "manual_unclosed",
            "currency": "Credits -> external payout",
            "source": "handlers/withdraw_request_handler.py",
            "notes": "Requests and approval markers exist; external settlement is not automated.",
            "evidence": _exists("handlers/withdraw_request_handler.py"),
        },
    ]


def income_status() -> dict:
    paths = income_paths()
    automated = [row for row in paths if row["status"].endswith("automated")]
    manual = [row for row in paths if row["status"] == "manual_unclosed"]
    blocked = [row for row in paths if row["status"] == "paused"]
    return {
        "priority": "P0",
        "definition": "confirmed external payment/deposit paths only; internal Credits activity is not cash revenue",
        "paths": paths,
        "summary": {
            "automated_external_paths": len(automated),
            "manual_unclosed_paths": len(manual),
            "paused_paths": len(blocked),
        },
    }
