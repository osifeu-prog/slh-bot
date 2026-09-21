"""Idempotent fulfillment for the SLH VIP launch bundle."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import state_manager
from core import economy_service
from store.grant_engine import apply_grant


VIP_MONTHLY_CREDITS = 300
VIP_LAUNCH_DEADLINE = datetime(
    2026, 10, 31, 23, 59, 59, tzinfo=ZoneInfo("Asia/Jerusalem")
)
VIP_BASE_AGENT_LIMIT = 2
VIP_LAUNCH_AGENT_LIMIT = 4
VIP_BUNDLE_VERSION = "2026-launch-v1"


def is_launch_offer_open(now: datetime | None = None) -> bool:
    if now is None:
        now = datetime.now(ZoneInfo("Asia/Jerusalem"))
    if now.tzinfo is None:
        now = now.replace(tzinfo=ZoneInfo("Asia/Jerusalem"))
    return now.astimezone(ZoneInfo("Asia/Jerusalem")) <= VIP_LAUNCH_DEADLINE


def _mark_bundle_status(
    uid: str,
    charge_id: str,
    *,
    launch_offer_qualified: bool,
    status: str,
    details: dict | None = None,
):
    def mutate(db):
        user = db.setdefault("users", {}).setdefault(uid, {})
        bundle = user.setdefault("vip_bundle", {})
        bundle.update(
            {
                "version": VIP_BUNDLE_VERSION,
                "launch_offer_qualified": bool(launch_offer_qualified),
                "status": status,
                "last_charge_id": str(charge_id),
                "updated_at": datetime.utcnow().isoformat() + "Z",
            }
        )
        if details:
            bundle.setdefault("history", []).append(dict(details))
            bundle["history"] = bundle["history"][-20:]
        return dict(bundle)

    return state_manager.atomic_update(mutate)


def _already_qualified(uid: str) -> bool:
    db = state_manager.load_db()
    user = db.get("users", {}).get(str(uid), {})
    return bool(
        user.get("vip_bundle", {}).get("launch_offer_qualified")
        or user.get("vip_launch_offer_qualified")
    )


def apply_vip_benefits(
    *,
    uid: str,
    charge_id: str,
    launch_offer_qualified: bool,
) -> dict:
    uid = str(uid).strip()
    charge_id = str(charge_id).strip()
    if not uid or not charge_id:
        raise ValueError("INVALID_VIP_FULFILLMENT_INPUT")

    qualified = bool(launch_offer_qualified) or _already_qualified(uid)
    if not qualified:
        return {"status": "skipped", "launch_offer_qualified": False}

    steps = {}
    try:
        plugin_result = apply_grant(
            uid,
            {"plugin": "agent_os"},
            purchase_id=f"vip:{charge_id}:agent_os",
        )
        steps["agent_os"] = plugin_result.get("ok") is True

        emoji_result = apply_grant(
            uid,
            {"digital": "emoji_vip"},
            purchase_id=f"vip:{charge_id}:emoji_vip",
        )
        steps["emoji_vip"] = emoji_result.get("ok") is True

        credits = economy_service.record_transaction(
            uid=uid,
            amount=VIP_MONTHLY_CREDITS,
            reason="vip:monthly_credits",
            meta={
                "idempotency_key": f"vip:{charge_id}:credits",
                "vip_bundle_version": VIP_BUNDLE_VERSION,
                "launch_offer": True,
            },
        )
        steps["credits"] = credits == _get_credits(uid) or credits is not None

        bundle = _mark_bundle_status(
            uid,
            charge_id,
            launch_offer_qualified=True,
            status="completed",
            details={
                "charge_id": charge_id,
                "credits": VIP_MONTHLY_CREDITS,
                "agent_os": steps["agent_os"],
                "emoji_vip": steps["emoji_vip"],
            },
        )
        return {
            "status": "completed",
            "launch_offer_qualified": True,
            "bundle": bundle,
            "steps": steps,
        }
    except Exception as exc:
        _mark_bundle_status(
            uid,
            charge_id,
            launch_offer_qualified=True,
            status="pending",
            details={"charge_id": charge_id, "error": type(exc).__name__, **steps},
        )
        return {
            "status": "pending",
            "launch_offer_qualified": True,
            "reason": type(exc).__name__,
            "steps": steps,
        }


def _get_credits(uid: str):
    try:
        return economy_service.get_balance_safe(uid)
    except Exception:
        return None


def user_has_launch_vip(uid: str, now: int | None = None) -> bool:
    import time

    now = int(time.time() if now is None else now)
    if _already_qualified(str(uid)):
        db = state_manager.load_db()
        user = db.get("users", {}).get(str(uid), {})
        return int(user.get("vip_access_until", 0) or 0) > now
    return False