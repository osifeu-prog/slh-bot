import json
import re
import secrets
from pathlib import Path
from datetime import datetime, timezone, timedelta

import state_manager
from core.authority import is_owner

DB_PATH = Path("state/db.json")
DEV_PATH = Path("state/devices.json")
LICENSE_ID_PATTERN = re.compile(r"SLH-LIC-[0-9A-F]{12}")
_PURCHASE_COLLECTIONS = (
    "purchases",
    "purchase_history",
    "purchase_records",
    "store_purchases",
    "device_purchases",
    "purchases_archive",
    "star_item_orders",
)
_REVOKED_SECRET_FIELDS = {"activation_code", "mqtt_password"}


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

    owner_uid = str(owner_uid)
    device = devices[device_id]
    licenses = db.setdefault("esp_licenses", {})
    existing_key = device.get("license_key")

    if existing_key and existing_key in licenses:
        existing = licenses[existing_key]
        if str(existing.get("owner_id")) != owner_uid:
            return {"ok": False, "error": "LICENSE_OWNER_MISMATCH"}
        if str(existing.get("status", "")).lower() != "revoked":
            return {"ok": True, "license": existing, "already_exists": True}

    # Reuse a prior license only if it remains valid. Revoked records are
    # retained for audit, but a new issuance must get a new license ID.
    for existing in reversed(list(licenses.values())):
        if existing.get("device_id") != device_id:
            continue
        if str(existing.get("owner_id")) != owner_uid:
            return {"ok": False, "error": "LICENSE_OWNER_MISMATCH"}
        if str(existing.get("status", "")).lower() == "revoked":
            continue
        device["license_key"] = existing.get("license_id")
        device["activation_code"] = existing.get("activation_code")
        device.pop("mqtt_password", None)
        device["license_status"] = existing.get("status", "sold")
        device["owner"] = owner_uid
        _save_json(DEV_PATH, dev_data)
        return {"ok": True, "license": existing, "already_exists": True}

    activation_code = generate_activation_code()
    license_key = generate_license_key()
    now = datetime.now(timezone.utc)
    lic = {
        "license_id": license_key,
        "device_id": device_id,
        "owner_id": owner_uid,
        "activation_code": activation_code,
        "status": "sold",
        "issued_at": now.isoformat(),
        "expires_at": (now + timedelta(days=duration_days)).isoformat() if duration_days else None,
        "activated_at": None,
        "mqtt_username": f"esp_{device_id.lower()}",
        "mqtt_password": secrets.token_hex(8),
        "duration_days": duration_days,
    }
    licenses[license_key] = lic
    device["license_key"] = license_key
    device["activation_code"] = activation_code
    device.pop("mqtt_password", None)
    device["license_status"] = "sold"
    device["owner"] = owner_uid
    _save_json(DB_PATH, db)
    _save_json(DEV_PATH, dev_data)
    return {"ok": True, "license": lic, "already_exists": False}


def activate_license(device_id, activation_code):
    db = _load_json(DB_PATH, {})
    dev_data = _load_json(DEV_PATH, {"devices": {}})
    devices = dev_data.get("devices", {})
    if device_id not in devices:
        return {"ok": False, "error": "DEVICE_NOT_FOUND"}

    licenses = db.get("esp_licenses", {})
    current_key = str((devices.get(device_id) or {}).get("license_key") or "")
    lic = licenses.get(current_key) if current_key else None
    if not isinstance(lic, dict) or lic.get("device_id") != device_id:
        # Legacy devices without a current pointer use the newest matching
        # non-revoked license, never the first historical record.
        lic = next(
            (
                item for item in reversed(list(licenses.values()))
                if isinstance(item, dict)
                and item.get("device_id") == device_id
                and str(item.get("status", "")).lower() != "revoked"
            ),
            None,
        )
    if not lic:
        return {"ok": False, "error": "LICENSE_NOT_FOUND"}
    if str(lic.get("status", "")).lower() == "revoked":
        return {"ok": False, "error": "LICENSE_REVOKED"}
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
    dev_data = _load_json(DEV_PATH, {"devices": {}})
    devices = dev_data.get("devices", {}) if isinstance(dev_data, dict) else {}
    current_key = str((devices.get(device_id) or {}).get("license_key") or "")
    db = _load_json(DB_PATH, {})
    licenses = db.get("esp_licenses", {})
    if current_key and isinstance(licenses, dict):
        current = licenses.get(current_key)
        if isinstance(current, dict) and current.get("device_id") == device_id:
            return current
    if isinstance(licenses, dict):
        for item in reversed(list(licenses.values())):
            if isinstance(item, dict) and item.get("device_id") == device_id:
                return item
    return None


def _contains_license_identity(value, license_id, device_id=None):
    """Match purchase records by exact license ID, never device ID alone.

    A device can receive a replacement license. Revoking an old license must
    not erase credentials from the new license's purchase record just because
    both records refer to the same physical device.
    """
    target = str(license_id or "").strip().upper()
    if isinstance(value, dict):
        if str(value.get("license_id") or "").strip().upper() == target:
            return True
        if str(value.get("license_key") or "").strip().upper() == target:
            return True
        return any(
            _contains_license_identity(child, target)
            for child in value.values()
        )
    if isinstance(value, list):
        return any(_contains_license_identity(child, target) for child in value)
    return False


def _scrub_license_secrets(value):
    """Delete only activation/password fields in a record already matched to a license."""
    removed = set()
    if isinstance(value, dict):
        for key in list(value):
            if str(key).lower() in _REVOKED_SECRET_FIELDS:
                removed.add(str(key).lower())
                value.pop(key, None)
            else:
                removed.update(_scrub_license_secrets(value[key]))
    elif isinstance(value, list):
        for child in value:
            removed.update(_scrub_license_secrets(child))
    return removed


def revoke_license(license_id, actor_uid):
    """Owner-only license revocation, secret scrubbing and append-only audit.

    The operation changes the canonical license record and only purchase copies
    that contain this exact license/device identity. It never modifies user
    balances or financial ledgers, and never returns or logs secret values.
    """
    license_id = str(license_id or "").strip().upper()
    actor_uid = str(actor_uid or "")
    if not LICENSE_ID_PATTERN.fullmatch(license_id):
        return {"status": "INVALID_LICENSE_ID"}
    if not is_owner(actor_uid):
        return {"status": "FORBIDDEN"}

    # Read the device registry only as a validated snapshot. If the registry
    # cannot be read, the canonical DB can still revoke the credential; sync
    # status will explain that manual remediation is required.
    try:
        device_snapshot = state_manager.load_json("devices.json", default=None)
    except Exception:
        device_snapshot = None
    registry_valid = (
        isinstance(device_snapshot, dict)
        and isinstance(device_snapshot.get("devices"), dict)
    )

    now = datetime.now(timezone.utc).isoformat()

    def mutate(db):
        licenses = db.get("esp_licenses")
        if not isinstance(licenses, dict):
            return {"status": "LICENSE_NOT_FOUND"}

        record = licenses.get(license_id)
        if not isinstance(record, dict):
            record = next(
                (
                    item for item in licenses.values()
                    if isinstance(item, dict) and str(item.get("license_id") or "").upper() == license_id
                ),
                None,
            )
        if not isinstance(record, dict):
            return {"status": "LICENSE_NOT_FOUND"}

        device_id = str(record.get("device_id") or "").strip()
        if not device_id:
            return {"status": "LICENSE_RECORD_INVALID"}

        audit = db.get("esp_license_security_audit", [])
        if not isinstance(audit, list):
            return {"status": "LICENSE_AUDIT_REGISTRY_INVALID"}

        already_revoked = str(record.get("status", "")).lower() == "revoked"
        removed = set()
        for key in _REVOKED_SECRET_FIELDS:
            if key in record:
                removed.add(key)
                record.pop(key, None)
        record["status"] = "revoked"
        record.setdefault("revoked_at", now)
        record["revoked_by"] = actor_uid

        purchase_records_scrubbed = 0
        for collection_name in _PURCHASE_COLLECTIONS:
            collection = db.get(collection_name)
            if isinstance(collection, dict):
                records = list(collection.values())
            elif isinstance(collection, list):
                records = collection
            else:
                continue
            for purchase in records:
                if not isinstance(purchase, (dict, list)):
                    continue
                if not _contains_license_identity(purchase, license_id, device_id):
                    continue
                fields = _scrub_license_secrets(purchase)
                if fields:
                    purchase_records_scrubbed += 1
                    removed.update(fields)

        db["esp_license_security_audit"] = audit
        audit.append({
            "at": now,
            "action": "license_revoked_and_secrets_scrubbed",
            "license_id_suffix": license_id[-6:],
            "device_id": device_id,
            "actor_uid": actor_uid,
            "already_revoked": already_revoked,
            "secrets_removed": sorted(removed),
            "purchase_records_scrubbed": purchase_records_scrubbed,
        })
        return {
            "status": "REVOKED",
            "device_id": device_id,
            "license_id_suffix": license_id[-6:],
            "secrets_removed": sorted(removed),
            "purchase_records_scrubbed": purchase_records_scrubbed,
            "already_revoked": already_revoked,
        }

    result = state_manager.atomic_update(mutate)
    if not isinstance(result, dict) or result.get("status") != "REVOKED":
        return result if isinstance(result, dict) else {"status": "LICENSE_REVOCATION_FAILED"}

    device_id = result["device_id"]
    device_synced = False
    if registry_valid:
        def mutate_devices(data):
            devices = data.get("devices") if isinstance(data, dict) else None
            if not isinstance(devices, dict):
                return False
            device = devices.get(device_id)
            if not isinstance(device, dict):
                return False
            current_key = str(device.get("license_key") or "")
            # A newer license may already be current; do not revoke or erase its
            # separate credentials while cleaning an older license.
            if current_key and current_key != license_id:
                return True
            device["license_status"] = "revoked"
            device.setdefault("license_revoked_at", now)
            device.pop("activation_code", None)
            device.pop("mqtt_password", None)
            return True

        try:
            device_synced = bool(state_manager.atomic_json_update(
                "devices.json", mutate_devices, default=None
            ))
        except Exception:
            device_synced = False

    result["status"] = "REVOKED" if device_synced else "REVOKED_DEVICE_SYNC_PENDING"
    return result
