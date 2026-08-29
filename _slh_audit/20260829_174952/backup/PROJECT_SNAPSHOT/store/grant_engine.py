import json
import time
from pathlib import Path
from core import profile_manager
from core.esp_license import issue_license


def apply_grant(uid, grant):
    user = profile_manager.get_user(uid)

    if "permission" in grant:
        perms = user.get("permissions", [])

        if grant["permission"] not in perms:
            perms.append(grant["permission"])

        profile_manager.update_user(uid, {
            "permissions": perms
        })

        return {
            "type": "permission",
            "value": grant["permission"]
        }

    if "course" in grant:
        profile_manager.update_user(uid, {
            "active_course": grant["course"]
        })

        return {
            "type": "course",
            "value": grant["course"]
        }

    if "hardware" in grant:
        device_id = f"ESP_{int(time.time())}"
        address = f"SLH_ESP_{device_id}"

        dev_path = Path("state/devices.json")
        try:
            dev_data = json.loads(dev_path.read_text(encoding="utf-8"))
        except Exception:
            dev_data = {"devices": {}}

        dev_data.setdefault("devices", {})[device_id] = {
            "name": f"ESP_{int(time.time())}",
            "type": "esp32",
            "status": "new",
            "owner": str(uid),
            "verified": False,
            "wallet_address": address,
            "agent_id": "7",
            "capabilities": ["sensor", "wallet", "signing"],
            "registered": time.time(),
        }
        dev_path.write_text(json.dumps(dev_data, ensure_ascii=False, indent=2), encoding="utf-8")

        db_path = Path("state/db.json")
        try:
            db = json.loads(db_path.read_text(encoding="utf-8"))
        except Exception:
            db = {}

        db.setdefault("device_wallets", {})[device_id] = {
            "address": address,
            "credits": 0,
            "staked": 0,
            "token_balance": 0,
            "owner": str(uid),
        }
        db.setdefault("device_agent_map", {})[device_id] = "7"

        hw_id = grant["hardware"]
        for pid in ("esp32_pro", "esp32_standard"):
            pkg = db.get("products", {}).get(pid)
            if pkg and pkg.get("type") == "hardware":
                inv = int(pkg.get("inventory", 0))
                if pid == hw_id and inv > 0:
                    pkg["inventory"] = inv - 1

        db_path.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")

        license_result = issue_license(device_id, str(uid), duration_days=365)
        license_data = license_result.get("license") if license_result.get("ok") else None

        return {
            "type": "hardware",
            "device_id": device_id,
            "wallet": address,
            "agent_id": "7",
            "license": license_data
        }

    return None
