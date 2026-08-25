import json
import time
from datetime import datetime, timezone
import paho.mqtt.client as mqtt

MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883


def load_db():
    try:
        with open("state/db.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def load_devices():
    try:
        with open("state/devices.json", "r", encoding="utf-8") as f:
            return json.load(f).get("devices", {})
    except Exception:
        return {}


def save_devices(devices):
    try:
        with open("state/devices.json", "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {"devices": {}}

    data["devices"] = devices

    with open("state/devices.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


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
            dev["status"] = "offline"
        else:
            reply = response
            dev["status"] = "online"

        dev["last_heartbeat"] = datetime.now(timezone.utc).isoformat()
        save_devices(devices)

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
        dev["status"] = "active"
        dev["verified"] = True
        dev["activated_at"] = datetime.now(timezone.utc).isoformat()
        save_devices(devices)
        bot.reply_to(msg, f"✅ {device_id} הופעל")

    @bot.message_handler(commands=["esp_heartbeat"])
    def esp_heartbeat(msg):
        parts = msg.text.split()
        device_id = parts[1] if len(parts) > 1 else "esp32_01"
        devices = load_devices()
        dev = devices.get(device_id)
        if not dev:
            bot.reply_to(msg, "מכשיר לא נמצא")
            return
        dev["status"] = "online"
        dev["last_heartbeat"] = datetime.now(timezone.utc).isoformat()
        save_devices(devices)
        bot.reply_to(msg, f"❤️ heartbeat: {device_id}")
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
                f"🆔 {did}\n"
                f"💳 Wallet: {address}\n"
                f"🤖 Agent: {agent_id}\n"
                "──────────────"
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
