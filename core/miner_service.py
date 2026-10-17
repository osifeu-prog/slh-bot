"""Authenticated miner telemetry stored on existing canonical device records.

The canonical registry is state_manager.load_db()["devices"].
Telemetry lives under devices[device_id]["telemetry"]; no parallel "miners"
registry is created. This module never mutates financial balances or ledgers.
"""
from __future__ import annotations

import hmac
import json
import math
import os
import re
from datetime import datetime, timezone
from typing import Any

import state_manager

_DEVICE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$")
_ESP_TYPES = {"esp32", "miner", "esp32_miner", "esp32-miner"}


class MinerTelemetryError(Exception):
    """Expected ingestion error with a safe public code and HTTP status."""

    def __init__(self, code: str, status_code: int):
        super().__init__(code)
        self.code = code
        self.status_code = status_code


def _device_token_map() -> dict[str, str] | None:
    raw = str(os.getenv("SLH_MINER_DEVICE_TOKENS_JSON", "") or "").strip()
    if not raw:
        return None
    try:
        mapping = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise MinerTelemetryError("MINER_TOKEN_CONFIG_INVALID", 503) from exc
    if not isinstance(mapping, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in mapping.items()):
        raise MinerTelemetryError("MINER_TOKEN_CONFIG_INVALID", 503)
    return {key.strip(): value.strip() for key, value in mapping.items()}


def _device_allowlist() -> set[str]:
    return {
        item.strip()
        for item in str(os.getenv("SLH_MINER_DEVICE_IDS", "") or "").split(",")
        if item.strip()
    }


def device_role_enabled(device_id: str, device: dict[str, Any]) -> bool:
    """Return true only for explicitly enrolled miner nodes.

    Per-device tokens and SLH_MINER_DEVICE_IDS are explicit opt-ins.
    Generic ESP32 records are not implicitly treated as miners.
    """
    token_map = _device_token_map()
    if token_map is not None and str(device_id) in token_map:
        return bool(token_map[str(device_id)])
    if str(device_id) in _device_allowlist():
        return True
    if device.get("miner_enabled") is True:
        return True
    capabilities = device.get("capabilities", [])
    if isinstance(capabilities, (list, tuple, set)) and "miner" in {
        str(item).strip().lower() for item in capabilities
    }:
        return True
    return str(device.get("type", "") or "").strip().lower() in {
        "miner", "esp32_miner", "esp32-miner"
    }


def _load_canonical_devices() -> dict[str, dict[str, Any]]:
    try:
        db = state_manager.load_db()
    except Exception as exc:
        raise MinerTelemetryError("MINER_DEVICE_REGISTRY_UNAVAILABLE", 503) from exc
    if not isinstance(db, dict) or not isinstance(db.get("devices"), dict):
        raise MinerTelemetryError("MINER_DEVICE_REGISTRY_INVALID", 503)
    return {
        str(device_id): device
        for device_id, device in db["devices"].items()
        if isinstance(device, dict)
    }


def get_registered_device(device_id: str) -> dict[str, Any] | None:
    return _load_canonical_devices().get(str(device_id))


def list_registered_esp_devices() -> dict[str, dict[str, Any]]:
    return {
        device_id: dict(device)
        for device_id, device in _load_canonical_devices().items()
        if str(device.get("type", "") or "").strip().lower() in _ESP_TYPES
    }


def _registered_device(device_id: str) -> dict[str, Any]:
    device = get_registered_device(device_id)
    if device is None:
        raise MinerTelemetryError("MINER_DEVICE_NOT_REGISTERED", 404)
    if str(device.get("type", "") or "").strip().lower() not in _ESP_TYPES:
        raise MinerTelemetryError("MINER_DEVICE_TYPE_NOT_ALLOWED", 403)
    if not str(device.get("owner_id") or device.get("owner") or "").strip():
        raise MinerTelemetryError("MINER_DEVICE_OWNER_REQUIRED", 403)
    if not device_role_enabled(device_id, device):
        raise MinerTelemetryError("MINER_ROLE_NOT_ENABLED", 403)
    return device


def _configured_token(device_id: str) -> str:
    token_map = _device_token_map()
    if token_map is not None:
        expected = str(token_map.get(device_id, "") or "").strip()
        if not expected:
            raise MinerTelemetryError("MINER_DEVICE_TOKEN_NOT_CONFIGURED", 403)
        return expected

    expected = str(os.getenv("SLH_MINER_INGEST_TOKEN", "") or "").strip()
    if not expected:
        raise MinerTelemetryError("MINER_INGEST_NOT_CONFIGURED", 503)
    return expected


def _authenticate(device_id: str, authorization: str) -> None:
    expected = _configured_token(device_id)
    scheme, separator, supplied = str(authorization or "").strip().partition(" ")
    supplied = supplied.strip()
    if not separator or scheme.lower() != "bearer" or not supplied:
        raise MinerTelemetryError("MINER_AUTH_REQUIRED", 401)
    if not hmac.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8")):
        raise MinerTelemetryError("MINER_AUTH_INVALID", 401)


def _number(
    payload: dict[str, Any],
    keys: tuple[str, ...],
    *,
    required: bool,
    minimum: float,
    maximum: float,
    error_prefix: str,
) -> float | None:
    key = next((candidate for candidate in keys if candidate in payload), None)
    if key is None or payload.get(key) is None:
        if required:
            raise MinerTelemetryError(f"{error_prefix}_REQUIRED", 400)
        return None
    value = payload.get(key)
    if isinstance(value, bool):
        raise MinerTelemetryError(f"{error_prefix}_INVALID", 400)
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise MinerTelemetryError(f"{error_prefix}_INVALID", 400) from exc
    if not math.isfinite(result) or result < minimum or result > maximum:
        raise MinerTelemetryError(f"{error_prefix}_OUT_OF_RANGE", 400)
    return result


def _safe_text(payload: dict[str, Any], key: str, default: str, limit: int = 48) -> str:
    value = payload.get(key, default)
    if value is None:
        return default
    if not isinstance(value, str):
        raise MinerTelemetryError(f"{key.upper()}_INVALID", 400)
    value = value.strip()
    if len(value) > limit or any(ord(char) < 32 for char in value):
        raise MinerTelemetryError(f"{key.upper()}_INVALID", 400)
    return value or default


def _health(temperature_c: float, watts: float | None) -> tuple[str, list[str]]:
    """Derive advisory-only conditions; this never actuates a relay."""
    alerts: list[str] = []
    if temperature_c >= 85.0:
        alerts.append("TEMPERATURE_CRITICAL")
    elif temperature_c >= 75.0:
        alerts.append("TEMPERATURE_HIGH")
    if watts is not None and watts < 100.0:
        alerts.append("POWER_LOW_REVIEW")
    return ("ALERT" if alerts else "OK", alerts)


def ingest_telemetry(payload: dict[str, Any], authorization: str) -> dict[str, Any]:
    """Authenticate a registered and explicitly enrolled ESP32, then update its own record."""
    if not isinstance(payload, dict):
        raise MinerTelemetryError("JSON_OBJECT_REQUIRED", 400)
    device_id = payload.get("device_id")
    if not isinstance(device_id, str):
        raise MinerTelemetryError("DEVICE_ID_REQUIRED", 400)
    device_id = device_id.strip()
    if not _DEVICE_ID_RE.fullmatch(device_id):
        raise MinerTelemetryError("DEVICE_ID_INVALID", 400)

    _authenticate(device_id, authorization)
    _registered_device(device_id)

    temperature_c = _number(
        payload, ("temperature_c", "temperature", "temp"), required=True,
        minimum=-55.0, maximum=125.0, error_prefix="TEMPERATURE",
    )
    watts = _number(
        payload, ("watts", "power_watts"), required=False,
        minimum=0.0, maximum=25000.0, error_prefix="WATTS",
    )
    volts = _number(
        payload, ("volts", "voltage"), required=False,
        minimum=0.0, maximum=300.0, error_prefix="VOLTS",
    )
    amps = _number(
        payload, ("amps", "current_amps"), required=False,
        minimum=0.0, maximum=150.0, error_prefix="AMPS",
    )
    energy_kwh = _number(
        payload, ("energy_kwh", "kwh"), required=False,
        minimum=0.0, maximum=1_000_000_000.0, error_prefix="ENERGY_KWH",
    )
    miner_id = _safe_text(payload, "miner_id", device_id, limit=64)
    reported_status = _safe_text(payload, "status", "UNSPECIFIED", limit=48)
    health_status, alerts = _health(temperature_c, watts)
    received_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    record = {
        "device_id": device_id,
        "miner_id": miner_id,
        "temperature_c": temperature_c,
        "watts": watts,
        "volts": volts,
        "amps": amps,
        "energy_kwh": energy_kwh,
        "reported_status": reported_status,
        "health_status": health_status,
        "alerts": alerts,
        "last_seen": received_at,
        "source": "esp32_authenticated_http",
        "schema_version": 1,
    }

    def mutate(db: dict[str, Any]) -> dict[str, Any]:
        devices = db.get("devices")
        if not isinstance(devices, dict):
            raise MinerTelemetryError("MINER_DEVICE_REGISTRY_INVALID", 503)
        current = devices.get(device_id)
        if not isinstance(current, dict):
            raise MinerTelemetryError("MINER_DEVICE_NOT_REGISTERED", 404)
        if str(current.get("type", "") or "").strip().lower() not in _ESP_TYPES:
            raise MinerTelemetryError("MINER_DEVICE_TYPE_NOT_ALLOWED", 403)
        if not str(current.get("owner_id") or current.get("owner") or "").strip():
            raise MinerTelemetryError("MINER_DEVICE_OWNER_REQUIRED", 403)
        if not device_role_enabled(device_id, current):
            raise MinerTelemetryError("MINER_ROLE_NOT_ENABLED", 403)
        # Preserve identity, ownership, MQTT topics, licenses, and all other keys.
        current["telemetry"] = dict(record)
        current["last_telemetry_at"] = received_at
        return dict(record)

    try:
        saved = state_manager.atomic_update(mutate)
    except MinerTelemetryError:
        raise
    except Exception as exc:
        raise MinerTelemetryError("MINER_STATE_WRITE_FAILED", 503) from exc
    return saved if isinstance(saved, dict) else dict(record)


def get_miner_telemetry(device_id: str) -> dict[str, Any] | None:
    """Read the telemetry snapshot nested under the existing canonical device."""
    devices = _load_canonical_devices()
    device = devices.get(str(device_id))
    if not isinstance(device, dict):
        return None
    telemetry = device.get("telemetry")
    return dict(telemetry) if isinstance(telemetry, dict) else None
