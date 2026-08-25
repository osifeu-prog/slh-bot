import json
import secrets
from pathlib import Path
from datetime import datetime, timezone, timedelta

DB_PATH = Path("state/db.json")
DEV_PATH = Path("state/devices.json")

def _load_json(p, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default

def _save_json(p, data):
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def generate_activation_code():
    return "SLH-ACT-" + secrets.token_hex(4).upper()

def generate_license_key():
    return "SLH-LIC-" + secrets.token_hex(6).upper()

def issue_license(device_id, owner_uid, duration_days=365):
    db = _load_json(DB_PATH, {})
    dev_data = _load_json(DEV_PATH, {"devices": {}})
    devices = dev_data.setdefault("devices", {})

    if device_id not in devices:
        return {"ok": False, "error": "DEVICE_NOT_FOUND"}

    licenses = db.setdefault("esp_licenses", {})

    activation_code = generate_activation_code()
    license_key = generate_license_key()
    now = datetime.now(timezone.utc)
    issued_at = now.isoformat()
    expires_at = (now + timedelta(days=duration_days)).isoformat() if duration_days else None

    lic = {
        "license_id": license_key,
        "device_id": device_id,
        "owner_id": str(owner_uid),
        "activation_code": activation_code,
        "status": "sold",
        "issued_at": issued_at,
        "expires_at": expires_at,
        "activated_at": None,
        "mqtt_username": f"esp_{device_id.lower()}",
        "mqtt_password": secrets.token_hex(8),
        "duration_days": duration_days,
    }

    licenses[license_key] = lic

    devices[device_id]["license_key"] = license_key
    devices[device_id]["activation_code"] = activation_code
    devices[device_id]["license_status"] = "sold"
    devices[device_id]["owner"] = str(owner_uid)

    _save_json(DB_PATH, db)
    _save_json(DEV_PATH, dev_data)

    return {"ok": True, "license": lic}

def activate_license(device_id, activation_code):
    db = _load_json(DB_PATH, {})
    dev_data = _load_json(DEV_PATH, {"devices": {}})
    devices = dev_data.get("devices", {})

    if device_id not in devices:
        return {"ok": False, "error": "DEVICE_NOT_FOUND"}

    lic = None
    for item in db.get("esp_licenses", {}).values():
        if item.get("device_id") == device_id:
            lic = item
            break

    if not lic:
        return {"ok": False, "error": "LICENSE_NOT_FOUND"}

    if activation_code != lic.get("activation_code"):
        return {"ok": False, "error": "INVALID_ACTIVATION_CODE"}

    if lic.get("status") == "activated":
        return {"ok": False, "error": "ALREADY_ACTIVATED"}

    now = datetime.now(timezone.utc)
    lic["status"] = "activated"
    lic["activated_at"] = now.isoformat()

    devices[device_id]["license_status"] = "activated"

    _save_json(DB_PATH, db)
    _save_json(DEV_PATH, dev_data)

    return {
        "ok": True,
        "license_id": lic["license_id"],
        "mqtt_username": lic["mqtt_username"],
        "mqtt_password": lic["mqtt_password"],
        "expires_at": lic["expires_at"],
    }

def get_license(device_id):
    db = _load_json(DB_PATH, {})
    for item in db.get("esp_licenses", {}).values():
        if item.get("device_id") == device_id:
            return item
    return None
