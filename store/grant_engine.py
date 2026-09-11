import json
import time
from pathlib import Path
from core import profile_manager
from core.esp_license import issue_license


def apply_grant(uid, grant, purchase_id=None):
    user = profile_manager.get_user(uid)

    if "permission" in grant:
        perms = user.get("permissions", [])
        if grant["permission"] not in perms:
            perms.append(grant["permission"])
            profile_manager.update_user(uid, {"permissions": perms})
        return {"ok": True, "type": "permission", "value": grant["permission"], "purchase_id": purchase_id}

    if "course" in grant:
        profile_manager.update_user(uid, {"active_course": grant["course"]})
        return {"ok": True, "type": "course", "value": grant["course"], "purchase_id": purchase_id}

    if "digital" in grant:
        inventory = user.get("inventory", {})
        digital_items = inventory.setdefault("digital", [])
        if grant["digital"] not in digital_items:
            digital_items.append(grant["digital"])
            profile_manager.update_user(uid, {"inventory": inventory})
        return {"ok": True, "type": "digital", "value": grant["digital"], "purchase_id": purchase_id}

    if "hardware" in grant:
        if not purchase_id:
            raise ValueError("PURCHASE_ID_REQUIRED")

        device_id = "ESP_PURCHASE_" + str(purchase_id).replace(":", "_")
        address = f"SLH_ESP_{device_id}"
        dev_path = Path("state/devices.json")
        try:
            dev_data = json.loads(dev_path.read_text(encoding="utf-8"))
        except Exception:
            dev_data = {"devices": {}}
        devices = dev_data.setdefault("devices", {})

        existing = devices.get(device_id)
        if existing:
            if str(existing.get("owner")) != str(uid):
                raise ValueError("DEVICE_OWNER_MISMATCH")
            license_result = issue_license(device_id, str(uid), duration_days=365)
            if not license_result.get("ok"):
                raise RuntimeError(license_result.get("error", "LICENSE_ISSUE_FAILED"))
            return {"ok": True, "type": "hardware", "device_id": device_id, "wallet": existing.get("wallet_address", address), "agent_id": existing.get("agent_id", "7"), "license": license_result.get("license"), "purchase_id": purchase_id, "already_exists": True}

        devices[device_id] = {
            "name": device_id,
            "type": "esp32",
            "status": "new",
            "owner": str(uid),
            "verified": False,
            "wallet_address": address,
            "agent_id": "7",
            "capabilities": ["sensor", "wallet", "signing"],
            "registered": time.time(),
            "purchase_id": purchase_id,
        }
        dev_path.write_text(json.dumps(dev_data, ensure_ascii=False, indent=2), encoding="utf-8")

        db_path = Path("state/db.json")
        try:
            db = json.loads(db_path.read_text(encoding="utf-8"))
        except Exception:
            db = {}
        db.setdefault("device_wallets", {})[device_id] = {"address": address, "credits": 0, "staked": 0, "token_balance": 0, "owner": str(uid), "purchase_id": purchase_id}
        db.setdefault("device_agent_map", {})[device_id] = "7"
        db_path.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")

        license_result = issue_license(device_id, str(uid), duration_days=365)
        if not license_result.get("ok"):
            raise RuntimeError(license_result.get("error", "LICENSE_ISSUE_FAILED"))
        return {"ok": True, "type": "hardware", "device_id": device_id, "wallet": address, "agent_id": "7", "license": license_result.get("license"), "purchase_id": purchase_id}

    return {"ok": False, "error": "UNSUPPORTED_GRANT", "purchase_id": purchase_id}
