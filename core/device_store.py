from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path


class DeviceStore:
    """Atomic, thread-safe persistence for the canonical device registry."""

    ROOT = Path(__file__).resolve().parent.parent
    PATH = ROOT / "state" / "devices.json"
    _lock = threading.RLock()

    def _load(self) -> dict:
        if not self.PATH.exists():
            return {"devices": {}}
        with self.PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("Device registry root must be an object")
        devices = data.get("devices")
        if not isinstance(devices, dict):
            data["devices"] = {}
        return data

    def _atomic_write(self, data: dict) -> None:
        self.PATH.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(
            prefix=f".{self.PATH.name}.",
            suffix=".tmp",
            dir=str(self.PATH.parent),
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.write("\n")
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.PATH)
        except Exception:
            try:
                os.unlink(tmp)
            except FileNotFoundError:
                pass
            raise

    @staticmethod
    def _normalize(device_id: str, device: dict) -> dict:
        result = dict(device)
        result["device_id"] = str(result.get("device_id", device_id))
        if "owner_id" not in result and "owner" in result:
            result["owner_id"] = str(result["owner"])
        result.setdefault("status", "offline")
        result.setdefault("capabilities", [])
        return result

    def get_all(self) -> dict[str, dict]:
        with self._lock:
            data = self._load()
            return {
                str(device_id): self._normalize(device_id, device)
                for device_id, device in data["devices"].items()
                if isinstance(device, dict)
            }

    def get(self, device_id: str) -> dict | None:
        return self.get_all().get(str(device_id))

    def owned_by(self, owner_id: str) -> dict[str, dict]:
        owner_id = str(owner_id)
        return {
            did: device
            for did, device in self.get_all().items()
            if str(device.get("owner_id", "")) == owner_id
        }

    def upsert(self, device_id: str, device: dict) -> dict:
        device_id = str(device_id)
        with self._lock:
            data = self._load()
            normalized = self._normalize(device_id, device)
            data["devices"][device_id] = normalized
            self._atomic_write(data)
            return normalized

    def delete(self, device_id: str) -> bool:
        device_id = str(device_id)
        with self._lock:
            data = self._load()
            if device_id not in data["devices"]:
                return False
            del data["devices"][device_id]
            self._atomic_write(data)
            return True
