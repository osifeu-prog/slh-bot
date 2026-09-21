"""Read-only device status model.

This module never mutates state/devices.json.
Live status is derived exclusively from fresh heartbeat/last_seen signals.
"""


import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

DEVICES_PATH = Path("state/devices.json")
DEFAULT_TTL_SECONDS = 120


def _timestamp(value: Any) -> float | None:
    if isinstance(value, (int, float)) and value > 0:
        return float(value)

    if isinstance(value, str) and value.strip():
        try:
            return datetime.fromisoformat(
                value.replace("Z", "+00:00")
            ).timestamp()
        except (TypeError, ValueError, OverflowError):
            return None

    return None


def get_device_status(
    target_name: str = "PC_Osif2",
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> dict[str, Any]:
    """Return a unified, read-only status for a logical device."""
    now = time.time()

    result: dict[str, Any] = {
        "name": target_name,
        "status": "unknown",
        "status_icon": "⚪️",
        "freshest_timestamp": None,
        "age_seconds": None,
        "ttl_seconds": ttl_seconds,
        "records": 0,
        "matched_ids": [],
        "source": "state/devices.json",
    }

    try:
        if not DEVICES_PATH.exists():
            result["status"] = "unknown"
            return result

        data = json.loads(DEVICES_PATH.read_text(encoding="utf-8"))
        devices = data.get("devices", {})

        freshest = None

        for device_id, device in devices.items():
            if not isinstance(device, dict):
                continue

            name = str(device.get("name", ""))
            if name != target_name and target_name.upper() not in str(device_id).upper():
                continue

            result["records"] += 1
            result["matched_ids"].append(device_id)

            candidates = (
                _timestamp(device.get("last_seen")),
                _timestamp(device.get("last_heartbeat")),
            )

            for ts in candidates:
                if ts is not None and (freshest is None or ts > freshest):
                    freshest = ts

        if freshest is None:
            result["status"] = "unknown"
            return result

        age = max(0.0, now - freshest)
        result["freshest_timestamp"] = freshest
        result["age_seconds"] = age

        if age <= ttl_seconds:
            result["status"] = "online"
            result["status_icon"] = "🟢"
        else:
            result["status"] = "offline"
            result["status_icon"] = "🔴"

        return result

    except Exception:
        # Read-model failures must never mutate state.
        return result


def get_device_bridge_status(
    target_name: str = "PC_Osif2",
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> str:
    return get_device_status(target_name, ttl_seconds)["status"]
