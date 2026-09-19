from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path
from datetime import datetime, timezone


class ProtectionPolicyStore:
    """Versioned per-device protection policy persistence."""

    ROOT = Path(__file__).resolve().parent.parent
    PATH = ROOT / "state" / "protection_policies.json"
    _lock = threading.RLock()

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _load(self) -> dict:
        if not self.PATH.exists():
            return {"policies": {}}
        with self.PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("Protection policy root must be an object")
        if not isinstance(data.get("policies"), dict):
            data["policies"] = {}
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

    def get(self, device_id: str) -> dict | None:
        with self._lock:
            return self._load()["policies"].get(str(device_id))

    def get_for_user(self, user_id: str) -> list[dict]:
        user_id = str(user_id)
        with self._lock:
            return [
                dict(policy)
                for policy in self._load()["policies"].values()
                if str(policy.get("user_id")) == user_id
            ]

    def put(self, user_id: str, device_id: str, patch: dict) -> dict:
        user_id, device_id = str(user_id), str(device_id)
        with self._lock:
            data = self._load()
            old = data["policies"].get(device_id, {})
            version = int(old.get("policy_version", 0)) + 1
            policy = {
                "policy_id": old.get("policy_id", f"POL_{device_id}"),
                "user_id": user_id,
                "device_id": device_id,
                "enabled": bool(patch.get("enabled", old.get("enabled", False))),
                "filter_sets": list(patch.get("filter_sets", old.get("filter_sets", []))),
                "allowlist": list(patch.get("allowlist", old.get("allowlist", []))),
                "blocklist": list(patch.get("blocklist", old.get("blocklist", []))),
                "policy_version": version,
                "updated_at": self._now(),
            }
            data["policies"][device_id] = policy
            self._atomic_write(data)
            return policy
