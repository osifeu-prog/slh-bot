import json
import time
from datetime import datetime, timezone
import paho.mqtt.client as mqtt

MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883

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

    @bot.message_handler(commands=["esp_status"])
    def esp_status(msg):
        devices = load_devices()
        if not devices:
            bot.reply_to(msg, "No devices registered.")
            return
        lines = [
            f"{did}: {d.get('status', '?')} | last: {d.get('last_heartbeat', d.get('last_seen', 'never'))}"
            for did, d in devices.items()
        ]
        bot.reply_to(msg, "\n".join(lines))
