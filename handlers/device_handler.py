import json, os, time, re
import state_manager
from core.authority import is_owner

def load_devices():
    try:
        data = state_manager.load_json("devices.json", default={"devices": {}})
        return data if isinstance(data, dict) else {"devices": {}}
    except Exception:
        return {"devices": {}}

def save_devices(data):
    def mutate(target):
        target.clear()
        target.update(data)
    return state_manager.atomic_json_update("devices.json", mutate, default={"devices": {}})

def generate_device_id(name):
    return f"DEV_{name.upper().replace(' ', '_')}_{int(time.time())}"

def _extract_hardware_uuid(text):
    match = re.search(
        r"(?i)(?:hardware_uuid=|uuid=)?([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
        text or "",
    )
    return match.group(1).upper() if match else None

def register_device(bot, m):
    parts = m.text.split(maxsplit=2)
    if len(parts) < 2:
        bot.reply_to(m, "Usage: /device_register <name> [description] [hardware_uuid=UUID]")
        return
    name = parts[1]
    tail = parts[2] if len(parts) > 2 else ""
    hardware_uuid = _extract_hardware_uuid(tail)
    desc = re.sub(
        r"(?i)(?:hardware_uuid=|uuid=)?[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        "",
        tail,
    ).strip() or "ESP32 Device"
    owner_id = str(m.from_user.id)
    normalized_name = name.strip().casefold()
    result = {}

    def mutate(data):
        devices = data.setdefault("devices", {})
        for did, d in devices.items():
            existing_owner = str(d.get("owner_id", d.get("owner", "")))
            existing_name = str(d.get("name", "")).strip().casefold()
            existing_uuid = _extract_hardware_uuid(str(d.get("hardware_uuid", "")))
            if hardware_uuid and existing_uuid == hardware_uuid:
                if existing_owner and existing_owner != owner_id and not is_owner(owner_id):
                    result["error"] = "❌ This hardware UUID is already registered to another owner"
                    return
                result["device_id"] = did
                result["existing"] = True
                return
            if existing_owner == owner_id and existing_name == normalized_name:
                result["device_id"] = did
                result["existing"] = True
                return

        device_id = generate_device_id(name)
        while device_id in devices:
            device_id = generate_device_id(name)
            time.sleep(0.001)
        devices[device_id] = {
            "name": name,
            "description": desc,
            "type": "esp32",
            "status": "offline",
            "capabilities": ["sensor", "wallet", "signing"],
            "registered": time.time(),
            "last_seen": None,
            "owner": owner_id,
            "owner_id": owner_id,
            "device_id": device_id,
            "permissions": ["receive_tasks", "report_status"],
        }
        if hardware_uuid:
            devices[device_id]["hardware_uuid"] = hardware_uuid
        result["device_id"] = device_id
        result["existing"] = False

    state_manager.atomic_json_update(
        "devices.json",
        mutate,
        default={"devices": {}},
    )
    if result.get("error"):
        bot.reply_to(m, result["error"])
        return
    device_id = result["device_id"]
    if result.get("existing"):
        bot.reply_to(m, f"ℹ️ Device '{name}' already registered (ID: {device_id})")
        return
    bot.reply_to(m, f"✅ Device '{name}' registered\n🆔 ID: {device_id}")

def list_devices(bot, m):
    data = load_devices()
    devices = data["devices"]
    if not devices:
        bot.reply_to(m, "📡 No devices registered")
        return
    lines = ["📡 SLH Devices:"]
    for did, d in devices.items():
        status_icon = "🟢" if d.get("status") == "online" else "🔴"
        lines.append(f"{status_icon} **{d['name']}** ({did})")
        lines.append(f"   Status: {d.get('status', 'unknown')}")
        lines.append(f"   Type: {d.get('type', 'unknown')}")
        lines.append(f"   Owner: {d.get('owner', 'unknown')}")
        lines.append("")
    bot.reply_to(m, "\n".join(lines), )

def device_status(bot, m):
    parts = m.text.split()
    if len(parts) < 2:
        bot.reply_to(m, "Usage: /device_status <device_id>")
        return
    device_id = parts[1]
    data = load_devices()
    devices = data["devices"]
    if device_id not in devices:
        bot.reply_to(m, f"❌ Device '{device_id}' not found")
        return
    d = devices[device_id]
    msg = f"""
📡 **Device Status**: {d['name']}
🆔 ID: {device_id}
📝 Description: {d.get('description', 'N/A')}
🟢 Status: {d.get('status', 'unknown')}
🕒 Registered: {time.ctime(d.get('registered', 0))}
🕒 Last Seen: {time.ctime(d.get('last_seen', 0)) if d.get('last_seen') else 'Never'}
👤 Owner: {d.get('owner', 'unknown')}
⚙️ Capabilities: {', '.join(d.get('capabilities', []))}
"""
    bot.reply_to(m, msg, )

def delete_device(bot, m):
    parts = m.text.split()
    if len(parts) < 2:
        bot.reply_to(m, "Usage: /device_delete <device_id>")
        return
    device_id = parts[1]
    data = load_devices()
    devices = data["devices"]
    if device_id not in devices:
        bot.reply_to(m, f"❌ Device '{device_id}' not found")
        return
    device = devices[device_id]
    owner_id = str(device.get("owner_id", device.get("owner", "")))
    caller_id = str(m.from_user.id)
    if owner_id and owner_id != caller_id and not is_owner(caller_id):
        bot.reply_to(m, "❌ You do not own this device")
        return
    name = device.get("name", device_id)
    del devices[device_id]
    save_devices(data)
    bot.reply_to(m, f"✅ Device '{name}' ({device_id}) deleted successfully")

def device_heartbeat(bot, m):
    # ESP32 sends heartbeat with device_id and status
    parts = m.text.split(maxsplit=2)
    if len(parts) < 2:
        bot.reply_to(m, "Usage: /device_heartbeat <device_id> [status]")
        return
    device_id = parts[1]
    status = parts[2] if len(parts) > 2 else "online"
    data = load_devices()
    devices = data["devices"]
    if device_id not in devices:
        bot.reply_to(m, f"❌ Device '{device_id}' not found")
        return
    device = devices[device_id]
    owner_id = str(device.get("owner_id", device.get("owner", "")))
    caller_id = str(m.from_user.id)
    if owner_id and owner_id != caller_id and not is_owner(caller_id):
        bot.reply_to(m, "❌ You do not own this device")
        return
    device.setdefault("device_id", device_id)
    if owner_id:
        device.setdefault("owner_id", owner_id)
    device["status"] = status
    device["last_seen"] = time.time()
    save_devices(data)
    bot.reply_to(m, f"✅ Device '{device_id}' heartbeat received. Status: {status}")

def register(bot, context):
    @bot.message_handler(commands=['device_register'])
    def device_register_cmd(m):
        register_device(bot, m)

    @bot.message_handler(commands=['device_list'])
    def device_list_cmd(m):
        list_devices(bot, m)

    @bot.message_handler(commands=['device_status'])
    def device_status_cmd(m):
        device_status(bot, m)

    @bot.message_handler(commands=['device_delete'])
    def device_delete_cmd(m):
        delete_device(bot, m)

    @bot.message_handler(commands=['device_heartbeat'])
    def device_heartbeat_cmd(m):
        device_heartbeat(bot, m)

    print("📡 Device handler loaded")
