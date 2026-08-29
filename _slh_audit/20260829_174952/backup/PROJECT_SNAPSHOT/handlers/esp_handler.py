import json
import os
import time
from datetime import datetime, timezone
import paho.mqtt.client as mqtt

try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False

MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883

DEVICES_FILE = "state/devices.json"
_DEVICES_LOCK_PATH = DEVICES_FILE + ".lock"


def load_db():
    try:
        with open("state/db.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def load_devices():
    try:
        with open(DEVICES_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get("devices", {})
    except Exception:
        return {}


def save_devices(devices):
    try:
        with open(DEVICES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {"devices": {}}
    data["devices"] = devices
    with open(DEVICES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def atomic_device_update(mutate_fn):
    os.makedirs("state", exist_ok=True)
    with open(_DEVICES_LOCK_PATH, "w") as lockfile:
        if HAS_FCNTL:
            fcntl.flock(lockfile, fcntl.LOCK_EX)
        try:
            devices = load_devices()
            result = mutate_fn(devices)
            save_devices(devices)
            return result
        finally:
            if HAS_FCNTL:
                fcntl.flock(lockfile, fcntl.LOCK_UN)


def register_esp_handler(bot):

    @bot.message_handler(commands=["esp_ping"])
    def esp_ping(msg):
        parts = msg.text.split()
        device_id = parts[1] if len(parts) > 1 else "esp32_01"
        devices = load_devices()
        dev = devices.get(device_id)
        if not dev:
            bot.reply_to(msg, f"Device {device_id} not found.")
            return
        if str(dev.get("owner")) != str(msg.from_user.id):
            bot.reply_to(msg, "אין לך הרשאה למכשיר זה")
            return

        topic = dev.get("mqtt_topic", f"slh/esp/{device_id}")
        command_topic = topic + "/command"
        response_topic = topic + "/response"
        response = None

        def on_connect(client, userdata, flags, rc):
            client.subscribe(response_topic)

        def on_message(client, userdata, msg):
            nonlocal response
            response = msg.payload.decode()
            client.disconnect()

        client = mqtt.Client()
        client.on_connect = on_connect
        client.on_message = on_message
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_start()
        time.sleep(0.5)
        client.publish(command_topic, "ping")
        time.sleep(2)
        client.loop_stop()
        client.disconnect()

        if response is None:
            reply = "No response"
            new_status = "offline"
        else:
            reply = response
            new_status = "online"

        def _mutate(devices, device_id=device_id, new_status=new_status):
            d = devices.get(device_id)
            if not d:
                return False
            d["status"] = new_status
            d["last_heartbeat"] = datetime.now(timezone.utc).isoformat()
            return True

        atomic_device_update(_mutate)
        bot.reply_to(msg, f"ESP32 {device_id}: {reply}")


    @bot.message_handler(commands=["esp_activate"])
    def esp_activate(msg):
        parts = msg.text.split()
        if len(parts) < 2:
            bot.reply_to(msg, "שימוש: /esp_activate <device_id>")
            return
        device_id = parts[1]
        devices = load_devices()
        dev = devices.get(device_id)
        if not dev:
            bot.reply_to(msg, "מכשיר לא נמצא")
            return
        if str(dev.get("owner")) != str(msg.from_user.id):
            bot.reply_to(msg, "אין לך הרשאה למכשיר זה")
            return

        def _mutate(devices, device_id=device_id):
            d = devices.get(device_id)
            if not d:
                return False
            d["status"] = "active"
            d["verified"] = True
            d["activated_at"] = datetime.now(timezone.utc).isoformat()
            return True

        atomic_device_update(_mutate)
        bot.reply_to(msg, f"{device_id} הופעל")

    @bot.message_handler(commands=["esp_heartbeat"])
    def esp_heartbeat(msg):
        parts = msg.text.split()
        device_id = parts[1] if len(parts) > 1 else "esp32_01"
        devices = load_devices()
        dev = devices.get(device_id)
        if not dev:
            bot.reply_to(msg, "מכשיר לא נמצא")
            return
        if str(dev.get("owner")) != str(msg.from_user.id):
            bot.reply_to(msg, "אין לך הרשאה למכשיר זה")
            return

        def _mutate(devices, device_id=device_id):
            d = devices.get(device_id)
            if not d:
                return False
            d["status"] = "online"
            d["last_heartbeat"] = datetime.now(timezone.utc).isoformat()
            return True

        atomic_device_update(_mutate)
        bot.reply_to(msg, f"heartbeat: {device_id}")


    @bot.message_handler(commands=["esp_progress"])
    def esp_progress(msg):
        parts = msg.text.split()
        if len(parts) < 2:
            bot.reply_to(msg, "שימוש: /esp_progress <device_id>")
            return
        device_id = parts[1]
        devices = load_devices()
        dev = devices.get(device_id)
        if not dev:
            bot.reply_to(msg, "מכשיר לא נמצא")
            return
        if str(dev.get("owner")) != str(msg.from_user.id):
            bot.reply_to(msg, "אין לך הרשאה למכשיר זה")
            return
        try:
            from core.esp_display import publish_progress
            ok, result = publish_progress(device_id)
            if ok:
                bot.reply_to(msg, f"נשלח ל-{device_id}\n{result}")
            else:
                bot.reply_to(msg, f"{result}")
        except Exception as e:
            bot.reply_to(msg, f"{e}")

    @bot.message_handler(commands=["esp_start"])
    def esp_start(msg):
        from core.identity import OWNER_TELEGRAM_ID
        import re
        import subprocess

        if int(msg.from_user.id) != int(OWNER_TELEGRAM_ID):
            bot.reply_to(msg, "OWNER only")
            return

        parts = msg.text.split()
        device_id = parts[1] if len(parts) > 1 else "DEV_ESP_NEW_1786177919"

        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", device_id):
            bot.reply_to(msg, "Invalid device_id")
            return

        devices = load_devices()
        if device_id not in devices:
            bot.reply_to(msg, "Device not registered")
            return

        log_path = f"/tmp/virtual_esp_{device_id}.log"
        with open(log_path, "a") as log_file:
            subprocess.Popen(
                ["python3", "core/virtual_esp.py", device_id],
                stdout=log_file,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        bot.reply_to(msg, f"{device_id} הופעל")

    @bot.message_handler(commands=["esp_stop"])
    def esp_stop(msg):
        from core.identity import OWNER_TELEGRAM_ID
        import re
        import subprocess

        if int(msg.from_user.id) != int(OWNER_TELEGRAM_ID):
            bot.reply_to(msg, "OWNER only")
            return

        parts = msg.text.split()
        device_id = parts[1] if len(parts) > 1 else "DEV_ESP_NEW_1786177919"

        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", device_id):
            bot.reply_to(msg, "Invalid device_id")
            return

        devices = load_devices()
        if device_id not in devices:
            bot.reply_to(msg, "Device not registered")
            return

        subprocess.run(
            ["pkill", "-f", f"virtual_esp.py {device_id}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        bot.reply_to(msg, f"{device_id} הופסק")


    @bot.message_handler(commands=["esp_broadcast_progress"])
    def esp_broadcast_progress(msg):
        try:
            from core.esp_broadcast import broadcast_progress
            result = broadcast_progress()
            bot.reply_to(msg, result)
        except Exception as e:
            bot.reply_to(msg, f"{e}")

    @bot.message_handler(commands=["esp_status"])
    def esp_status(msg):
        devices = load_devices()
        if not devices:
            bot.reply_to(msg, "No devices registered.")
            return

        db = load_db()
        device_wallets = db.get("device_wallets", {})
        device_agent_map = db.get("device_agent_map", {})
        lines = []
        for did, d in devices.items():
            if d.get("type") != "esp32":
                continue
            status = d.get("status", "?")
            wallet = device_wallets.get(did, {})
            address = d.get("wallet_address") or wallet.get("address", "-")
            agent_id = d.get("agent_id") or device_agent_map.get(did, "-")
            lines.append(
                f"{d.get('name', did)} [{status}]\n"
                f"{did}\n"
                f"Wallet: {address}\n"
                f"Agent: {agent_id}\n"
                "--------------"
            )

        try:
            with open("branding/SLH_LOGO.txt", "r", encoding="utf-8") as f:
                logo = f.read().strip()
        except Exception:
            logo = ""

        text = "\n".join(lines)
        if logo:
            text = logo + "\n\n" + text
        bot.reply_to(msg, text)