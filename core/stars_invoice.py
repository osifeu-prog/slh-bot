"""Canonical Telegram Stars invoice payloads and Mini App invoice creation."""
import os
import threading
import time
from typing import Any

import telebot
from telebot.types import LabeledPrice

import state_manager
from core.stars_price_authority import (
    CREDIT_PACKS_BY_ID,
    TELEGRAM_STARS_CURRENCY,
    VIP_MONTHLY_STARS,
    VIP_SUBSCRIPTION_PERIOD,
)
from store.engine import load_items, resolve_item_id
from store.stars_purchase_service import get_stars_price

_BOT_LOCK = threading.Lock()
_INVOICE_BOT = None


def _uid(uid: Any) -> str:
    value = str(uid or "").strip()
    if not value.isdigit():
        raise ValueError("INVALID_USER_ID")
    return value


def build_credit_payload(credits: int, uid: Any) -> str:
    return f"credits_{int(credits)}_{_uid(uid)}"


def build_item_payload(item_id: str, uid: Any) -> str:
    item = str(item_id or "").strip()
    if not item or len(item) > 80 or not all(ch.isalnum() or ch in "_-." for ch in item):
        raise ValueError("INVALID_ITEM_ID")
    return f"item_{item}_{_uid(uid)}"


def build_vip_payload(uid: Any) -> str:
    return f"vip_monthly_{_uid(uid)}"


def parse_invoice_payload(payload: Any) -> dict[str, Any] | None:
    raw = str(payload or "").strip()
    if not raw or len(raw.encode("utf-8")) > 128:
        return None
    parts = raw.split("_")
    if len(parts) == 3 and parts[0] == "credits" and parts[1].isdigit() and parts[2].isdigit():
        return {"kind": "credits", "credits": int(parts[1]), "uid": parts[2]}
    if len(parts) >= 3 and parts[0] == "item" and parts[-1].isdigit():
        item_id = "_".join(parts[1:-1]).strip()
        return {"kind": "item", "item_id": item_id, "uid": parts[-1]} if item_id else None
    if len(parts) == 3 and parts[0] == "vip" and parts[1] == "monthly" and parts[2].isdigit():
        return {"kind": "vip", "uid": parts[2]}
    return None


def _invoice_bot():
    global _INVOICE_BOT
    if _INVOICE_BOT is None:
        token = os.getenv("BOT_TOKEN", "").strip()
        if not token:
            raise RuntimeError("BOT_TOKEN_MISSING")
        with _BOT_LOCK:
            if _INVOICE_BOT is None:
                _INVOICE_BOT = telebot.TeleBot(token, parse_mode=None)
    return _INVOICE_BOT


def _bounded(value: str, limit: int) -> str:
    return value[:limit]


def _resolve_purchase(uid: str, kind: str, item_id: str) -> dict[str, Any]:
    if kind == "credit_pack":
        package = CREDIT_PACKS_BY_ID.get(item_id)
        if package is None:
            raise ValueError("CREDIT_PACK_NOT_FOUND")
        return {
            "kind": "credit_pack",
            "id": package.pack_id,
            "stars": int(package.stars),
            "title": "SLH Credits",
            "description": f"{package.credits} Credits — {package.label}",
            "payload": build_credit_payload(package.credits, uid),
            "subscription_period": None,
        }

    if kind == "store_item":
        items = load_items()
        canonical_id = resolve_item_id(item_id, items)
        if canonical_id is None:
            raise ValueError("ITEM_NOT_FOUND")
        stars = get_stars_price(canonical_id)
        if stars is None:
            raise ValueError("ITEM_NOT_AVAILABLE_FOR_STARS")
        item = items.get(canonical_id) or {}
        name = str(item.get("name", canonical_id))
        return {
            "kind": "store_item",
            "id": canonical_id,
            "stars": int(stars),
            "title": _bounded(name, 32),
            "description": _bounded("SLH Store — " + name, 255),
            "payload": build_item_payload(canonical_id, uid),
            "subscription_period": None,
        }

    if kind == "vip":
        if item_id != "vip_monthly":
            raise ValueError("VIP_PRODUCT_NOT_FOUND")
        db = state_manager.load_db()
        user = db.get("users", {}).get(uid, {}) if isinstance(db, dict) else {}
        try:
            active_until = int(user.get("vip_access_until", 0) or 0)
        except (TypeError, ValueError):
            active_until = 0
        if active_until > int(time.time()):
            raise ValueError("VIP_ALREADY_ACTIVE")
        return {
            "kind": "vip",
            "id": "vip_monthly",
            "stars": int(VIP_MONTHLY_STARS),
            "title": "SLH VIP",
            "description": "SLH VIP — מנוי חודשי ב-Telegram Stars",
            "payload": build_vip_payload(uid),
            "subscription_period": VIP_SUBSCRIPTION_PERIOD,
        }

    raise ValueError("INVALID_PURCHASE_KIND")


def create_invoice_link_for_purchase(*, uid: str, kind: str, item_id: str) -> dict[str, Any]:
    purchase = _resolve_purchase(_uid(uid), kind, item_id)
    bot = _invoice_bot()
    link = bot.create_invoice_link(
        title=purchase["title"],
        description=purchase["description"],
        payload=purchase["payload"],
        provider_token=None,
        currency=TELEGRAM_STARS_CURRENCY,
        prices=[LabeledPrice(label=purchase["title"], amount=purchase["stars"])],
        subscription_period=purchase["subscription_period"],
    )
    if not link:
        raise RuntimeError("TELEGRAM_INVOICE_LINK_EMPTY")
    return {
        "link": str(link),
        "kind": purchase["kind"],
        "id": purchase["id"],
        "stars": purchase["stars"],
        "currency": TELEGRAM_STARS_CURRENCY,
    }
