import json
import math
import time

import state_manager
from core import profile_manager
from core.authority import normalize_uid
from core.esp_license import issue_license


def _canonical_uid(uid):
    """Return the canonical Telegram user id or fail closed."""
    value = normalize_uid(uid).strip()
    if not value.isdigit():
        raise ValueError("CANONICAL_OWNER_ID_REQUIRED")
    return value



def _grant_vip_months(uid, purchase_id, months):
    """Grant complimentary VIP time once per immutable purchase ID; no revenue is recorded."""
    from core.stars_price_authority import VIP_SUBSCRIPTION_PERIOD

    uid = str(uid).strip()
    purchase_id = str(purchase_id or "").strip()
    if not uid or not purchase_id:
        raise ValueError("VIP_BONUS_PURCHASE_ID_REQUIRED")
    if isinstance(months, bool) or not isinstance(months, int) or months < 1 or months > 12:
        raise ValueError("VIP_BONUS_MONTHS_INVALID")

    award_id = f"store-bonus:{purchase_id}:vip-months"

    def mutate(db):
        users = db.get("users")
        if not isinstance(users, dict) or not isinstance(users.get(uid), dict):
            raise ValueError("VIP_BONUS_USER_NOT_FOUND")
        awards = db.setdefault("vip_bonus_awards", {})
        if not isinstance(awards, dict):
            raise ValueError("VIP_BONUS_AWARDS_INVALID")

        existing = awards.get(award_id)
        if existing is not None:
            if (
                not isinstance(existing, dict)
                or str(existing.get("uid")) != uid
                or int(existing.get("months", 0) or 0) != months
                or str(existing.get("purchase_id")) != purchase_id
            ):
                return {"status": "CONFLICT", "award_id": award_id}
            return {**existing, "status": "DUPLICATE"}

        user = users[uid]
        permissions = user.get("permissions", [])
        if permissions is None:
            permissions = []
        if not isinstance(permissions, list):
            raise ValueError("VIP_BONUS_PERMISSIONS_INVALID")
        try:
            previous_until = int(user.get("vip_access_until", 0) or 0)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("VIP_BONUS_EXPIRY_INVALID") from exc

        now = int(time.time())
        starts_at = max(now, previous_until)
        expires_at = starts_at + int(VIP_SUBSCRIPTION_PERIOD) * months
        if "vip_access" not in permissions:
            permissions = list(permissions) + ["vip_access"]
        user["permissions"] = permissions
        user["vip_access_until"] = expires_at

        record = {
            "award_id": award_id,
            "uid": uid,
            "purchase_id": purchase_id,
            "months": months,
            "period_seconds": int(VIP_SUBSCRIPTION_PERIOD),
            "granted_at": now,
            "starts_at": starts_at,
            "expires_at": expires_at,
            "source": "store_bundle_bonus",
        }
        awards[award_id] = record
        return {**record, "status": "APPLIED"}

    result = state_manager.atomic_update(mutate)
    if not isinstance(result, dict) or result.get("status") == "CONFLICT":
        raise ValueError("VIP_BONUS_IDEMPOTENCY_CONFLICT")
    return result


def _apply_bundle_grant(uid, grant, purchase_id=None):
    """Apply a small allowlisted bundle with replay-safe Credits/VIP bonuses."""
    allowed_fields = {"bundle", "credits_bonus", "vip_months_bonus"}
    if set(grant) - allowed_fields:
        raise ValueError("BUNDLE_GRANT_FIELDS_INVALID")

    grants = grant.get("bundle")
    if not isinstance(grants, list) or not grants or len(grants) > 16:
        raise ValueError("BUNDLE_GRANTS_INVALID")

    allowed_grant_types = {"permission", "course", "digital", "plugin", "hardware"}
    validated = []
    for item in grants:
        if not isinstance(item, dict) or len(item) != 1:
            raise ValueError("BUNDLE_CHILD_GRANT_INVALID")
        kind = next(iter(item))
        if kind not in allowed_grant_types or not str(item.get(kind) or "").strip():
            raise ValueError("BUNDLE_CHILD_GRANT_INVALID")
        validated.append({kind: item[kind]})

    raw_credits = grant.get("credits_bonus", 0)
    if isinstance(raw_credits, bool):
        raise ValueError("BUNDLE_CREDITS_BONUS_INVALID")
    try:
        credits_bonus = float(raw_credits)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("BUNDLE_CREDITS_BONUS_INVALID") from exc
    if not math.isfinite(credits_bonus) or credits_bonus < 0 or credits_bonus > 10000:
        raise ValueError("BUNDLE_CREDITS_BONUS_INVALID")

    raw_months = grant.get("vip_months_bonus", 0)
    if isinstance(raw_months, bool):
        raise ValueError("BUNDLE_VIP_MONTHS_INVALID")
    try:
        vip_months_bonus = int(raw_months)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("BUNDLE_VIP_MONTHS_INVALID") from exc
    if vip_months_bonus != raw_months or vip_months_bonus < 0 or vip_months_bonus > 12:
        raise ValueError("BUNDLE_VIP_MONTHS_INVALID")

    purchase_id = str(purchase_id or "").strip()
    if (credits_bonus > 0 or vip_months_bonus > 0) and not purchase_id:
        raise ValueError("BUNDLE_BONUS_PURCHASE_ID_REQUIRED")

    applied = []
    for index, child_grant in enumerate(validated):
        child_purchase_id = f"{purchase_id}:bundle:{index}" if purchase_id else None
        result = apply_grant(uid, child_grant, purchase_id=child_purchase_id)
        if not isinstance(result, dict) or result.get("ok") is not True:
            raise RuntimeError("BUNDLE_CHILD_FULFILLMENT_FAILED")
        applied.append(result)

    credits_result = None
    if credits_bonus > 0:
        from core import economy_service

        credits_result = economy_service.record_transaction(
            uid=uid,
            amount=credits_bonus,
            reason="store:bundle_bonus",
            meta={
                "idempotency_key": f"store-bonus:{purchase_id}:credits",
                "purchase_id": purchase_id,
                "source": "store_bundle",
            },
            return_details=True,
        )
        if not isinstance(credits_result, dict) or credits_result.get("status") not in {"APPLIED", "DUPLICATE"}:
            raise RuntimeError("BUNDLE_CREDITS_BONUS_FAILED")

    vip_result = None
    if vip_months_bonus > 0:
        vip_result = _grant_vip_months(uid, purchase_id, vip_months_bonus)

    return {
        "ok": True,
        "type": "bundle",
        "purchase_id": purchase_id or None,
        "grants": applied,
        "credits_bonus": credits_result,
        "vip_bonus": vip_result,
    }


def apply_grant(uid, grant, purchase_id=None):
    uid = _canonical_uid(uid)
    if not isinstance(grant, dict):
        raise ValueError("GRANT_INVALID")
    if "bundle" in grant:
        return _apply_bundle_grant(uid, grant, purchase_id=purchase_id)
    user = profile_manager.get_user(uid)

    if "permission" in grant:
        perms = user.get("permissions", [])
        if grant["permission"] not in perms:
            perms.append(grant["permission"])
            profile_manager.update_user(uid, {"permissions": perms})
        return {"ok": True, "type": "permission", "value": grant["permission"], "purchase_id": purchase_id}

    if "course" in grant:
        course_id = str(grant["course"]).strip()
        if not course_id:
            raise ValueError("COURSE_ID_REQUIRED")

        # Academy is the canonical course-entitlement state.
        # start_course creates a new enrollment or preserves existing progress.
        from core import academy_manager
        if not academy_manager.start_course(uid, course_id):
            raise ValueError("COURSE_NOT_FOUND")

        return {
            "ok": True,
            "type": "course",
            "value": course_id,
            "purchase_id": purchase_id,
            "academy_enrolled": True,
        }

    if "digital" in grant:
        inventory = user.get("inventory", {})
        digital_items = inventory.setdefault("digital", [])
        if grant["digital"] not in digital_items:
            digital_items.append(grant["digital"])
            profile_manager.update_user(uid, {"inventory": inventory})
        return {"ok": True, "type": "digital", "value": grant["digital"], "purchase_id": purchase_id}

    if "plugin" in grant:
        from plugins_store import install_plugin
        plugin_id = str(grant["plugin"]).strip()
        result = install_plugin(plugin_id)
        if not str(result).startswith("✅"):
            raise RuntimeError("PLUGIN_FULFILLMENT_FAILED")
        inventory = user.get("inventory", {})
        plugins = inventory.setdefault("plugins", [])
        if plugin_id not in plugins:
            plugins.append(plugin_id)
            profile_manager.update_user(uid, {"inventory": inventory})
        return {"ok": True, "type": "plugin", "value": plugin_id, "result": result, "purchase_id": purchase_id}

    if "hardware" in grant:
        if not purchase_id:
            raise ValueError("PURCHASE_ID_REQUIRED")

        device_id = "ESP_PURCHASE_" + str(purchase_id).replace(":", "_")
        address = f"SLH_ESP_{device_id}"

        def register_device(dev_data):
            if not isinstance(dev_data, dict):
                raise ValueError("DEVICES_STATE_INVALID")
            devices = dev_data.setdefault("devices", {})
            if not isinstance(devices, dict):
                raise ValueError("DEVICES_STATE_INVALID")

            existing = devices.get(device_id)
            if existing:
                if str(existing.get("owner")) != uid:
                    raise ValueError("DEVICE_OWNER_MISMATCH")
                return {
                    "already_exists": True,
                    "wallet": existing.get("wallet_address", address),
                    "agent_id": existing.get("agent_id", "7"),
                }

            devices[device_id] = {
                "name": device_id,
                "type": "esp32",
                "status": "new",
                "owner": uid,
                "verified": False,
                "wallet_address": address,
                "agent_id": "7",
                "capabilities": ["sensor", "wallet", "signing"],
                "registered": time.time(),
                "purchase_id": purchase_id,
            }
            return {"already_exists": False, "wallet": address, "agent_id": "7"}

        device_result = state_manager.atomic_json_update(
            "devices.json",
            register_device,
            default={"devices": {}},
        )

        if device_result["already_exists"]:
            license_result = issue_license(device_id, uid, duration_days=365)
            if not license_result.get("ok"):
                raise RuntimeError(license_result.get("error", "LICENSE_ISSUE_FAILED"))
            return {
                "ok": True,
                "type": "hardware",
                "device_id": device_id,
                "wallet": device_result["wallet"],
                "agent_id": device_result["agent_id"],
                "license": license_result.get("license"),
                "purchase_id": purchase_id,
                "already_exists": True,
            }

        def mutate_db(db):
            if not isinstance(db, dict) or "users" not in db:
                raise RuntimeError("DB_STATE_INVALID")
            db.setdefault("device_wallets", {})[device_id] = {
                "address": address,
                "credits": 0,
                "staked": 0,
                "token_balance": 0,
                "owner": uid,
                "purchase_id": purchase_id,
            }
            db.setdefault("device_agent_map", {})[device_id] = "7"
            return None

        state_manager.atomic_update(mutate_db)

        license_result = issue_license(device_id, uid, duration_days=365)
        if not license_result.get("ok"):
            raise RuntimeError(license_result.get("error", "LICENSE_ISSUE_FAILED"))
        return {
            "ok": True,
            "type": "hardware",
            "device_id": device_id,
            "wallet": address,
            "agent_id": "7",
            "license": license_result.get("license"),
            "purchase_id": purchase_id,
        }

    return {"ok": False, "error": "UNSUPPORTED_GRANT", "purchase_id": purchase_id}
