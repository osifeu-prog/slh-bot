"""Owner read-only PC and mesh status for SLH Control Plane."""
from __future__ import annotations

import json
from pathlib import Path

from core.authority import is_owner

DEVICES_PATH = Path("state/devices.json")


def _devices() -> dict:
    try:
        data = json.loads(DEVICES_PATH.read_text(encoding="utf-8"))
        value = data.get("devices", {})
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _owner(msg) -> bool:
    try:
        return bool(is_owner(msg.from_user.id))
    except Exception:
        return False


def _kind(device: dict) -> str:
    dtype = str(device.get("type", "")).lower()
    name = str(device.get("name", "")).lower()
    did = str(device.get("device_id", "")).lower()
    if dtype == "esp32" or "esp" in name or did.startswith("esp_"):
        return "ESP"
    if dtype in {"pc", "computer", "windows"} or did.startswith("PC_") or "pc" in name:
        return "PC"
    return str(device.get("type") or "OTHER").upper()


def _marker(status: str) -> str:
    return "🟢" if status.lower() == "online" else "🔴"


def register(bot, context=None):
    @bot.message_handler(commands=["pc", "pc_list"])
    def pc_cmd(msg):
        if not _owner(msg):
            bot.reply_to(msg, "⛔️ Owner only.")
            return
        devices = {k: v for k, v in _devices().items() if _kind(v) == "PC"}
        if not devices:
            bot.reply_to(msg, "🖥️ אין מחשבי SLH רשומים כרגע.")
            return
        lines = ["🖥️ SLH COMPUTERS", ""]
        for did, dev in sorted(devices.items()):
            status = str(dev.get("status", "unknown"))
            hb = dev.get("last_heartbeat") or dev.get("last_seen") or "—"
            lines.append(f"{_marker(status)} {dev.get('name', did)}")
            lines.append(f"   ID: {did}")
            lines.append(f"   Status: {status}")
            lines.append(f"   Last seen: {hb}")
        bot.reply_to(msg, "\n".join(lines)[:4000])

    @bot.message_handler(commands=["mesh"])
    def mesh_cmd(msg):
        if not _owner(msg):
            bot.reply_to(msg, "⛔️ Owner only.")
            return
        devices = _devices()
        pcs = [v for v in devices.values() if _kind(v) == "PC"]
        esps = [v for v in devices.values() if _kind(v) == "ESP"]
        online_pc = sum(str(v.get("status", "")).lower() == "online" for v in pcs)
        online_esp = sum(str(v.get("status", "")).lower() == "online" for v in esps)
        lines = [
            "🌐 SLH OS MESH",
            "",
            f"🖥️ PCs: {online_pc}/{len(pcs)} online",
            f"📡 ESP: {online_esp}/{len(esps)} online",
            f"📦 Registered devices: {len(devices)}",
            "",
            "Control Plane: SLH OS",
            "Financial ledger: canonical application state",
            "Remote command execution: separate owner-authorized path",
        ]
        bot.reply_to(msg, "\n".join(lines))

    print("✅ PC/Mesh read-only handler loaded")
