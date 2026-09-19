"""Canonical device persistence for SLH OS.

Keeps the legacy state/devices.json format readable while providing
atomic writes and a single access layer for Device/Protection features.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional


class DeviceStore:
    ROOT = Path(__file__).resolve().parent.parent
    PATH = ROOT / "state" / "devices.json"
    _lock = threading.RLock()

    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path else self.PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {"devices": {}}
        with self.path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("devices state root must be an object")
        devices = data.get("devices")
        if not isinstance(devices, dict):
            data["devices"] = {}
        return data

    def _atomic_write(self, data: Dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(
            prefix=f".{self.path.name}.",
            suffix=".tmp",
            dir=str(self.path.parent),
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.write("\n")
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.path)
        except Exception:
            try:
                os.unlink(tmp)
            except FileNotFoundError:
                pass
            raise

    @staticmethod
    def _normalize(device_id: str, device: Dict[str, Any]) -> Dict[str, Any]:
        result = dict(device)
        result["device_id"] = str(result.get("device_id") or device_id)
        # Preserve legacy "owner" while exposing the canonical owner_id.
        if not result.get("owner_id") and result.get("owner") is not None:
            result["owner_id"] = str(result["owner"])
        if result.get("owner_id") is not None:
            result["owner_id"] = str(result["owner_id"])
        return result

    def get(self, device_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            device = self._load()["devices"].get(str(device_id))
            return None if not isinstance(device, dict) else self._normalize(str(device_id), device)

    def list_for_user(self, user_id: str) -> Dict[str, Dict[str, Any]]:
        uid = str(user_id)
        with self._lock:
            devices = self._load()["devices"]
            return {
                str(device_id): self._normalize(str(device_id), device)
                for device_id, device in devices.items()
                if isinstance(device, dict)
                and str(device.get("owner_id", device.get("owner", ""))) == uid
            }

    def list_all(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            devices = self._load()["devices"]
            return {
                str(device_id): self._normalize(str(device_id), device)
                for device_id, device in devices.items()
                if isinstance(device, dict)
            }

    def create(self, device_id: str, device: Dict[str, Any]) -> Dict[str, Any]:
        did = str(device_id)
        with self._lock:
            data = self._load()
            if did in data["devices"]:
                raise ValueError(f"Device already exists: {did}")
            normalized = self._normalize(did, device)
            data["devices"][did] = normalized
            self._atomic_write(data)
            return normalized

    def update(self, device_id: str, changes: Dict[str, Any]) -> Dict[str, Any]:
        did = str(device_id)
        with self._lock:
            data = self._load()
            current = data["devices"].get(did)
            if not isinstance(current, dict):
                raise KeyError(f"Device not found: {did}")
            current.update(changes)
            normalized = self._normalize(did, current)
            data["devices"][did] = normalized
            self._atomic_write(data)
            return normalized

    def heartbeat(self, device_id: str, status: str = "online") -> Dict[str, Any]:
        return self.update(
            device_id,
            {"status": str(status), "last_seen": time.time()},
        )

    def delete(self, device_id: str) -> None:
        did = str(device_id)
        with self._lock:
            data = self._load()
            if did not in data["devices"]:
                raise KeyError(f"Device not found: {did}")
            # Physical deletion remains available for legacy admin tooling.
            # Protection will later use revoke/disable semantics instead.
            del data["devices"][did]
            self._atomic_write(data)
