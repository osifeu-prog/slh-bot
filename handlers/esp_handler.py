import json
import time
from datetime import datetime, timezone

MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
RESPONSES = {}
_mqtt_client = None

def _get_mqtt():
    global _mqtt_client
    if _mqtt_client is not None:
        return _mqtt_client
    try:
        import paho.mqtt.client as mqtt
        def on_message(client, userdata, msg):
            RESPONSES[msg.topic] = msg.payload.decode()
        c = mqtt.Client()
        c.on_message = on_message
        c.connect(MQTT_BROKER, MQTT_PORT, 60)
        c.subscribe("slh/esp/response/#")
        c.loop_start()
        _mqtt_client = c
    except Exception as e:
        print("MQTT unavailable:", e)
        _mqtt_client = None
    return _mqtt_client

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
        client = _get_mqtt()
        if client is None:
            bot.reply_to(msg, f"ESP32 {device_id}: MQTT unavailable")
            return
        client.publish(topic + "/command", "ping")
        time.sleep(2)
        reply = RESPONSES.get(topic + "/response", "No response")
        dev["last_heartbeat"] = datetime.now(timezone.utc).isoformat()
        dev["status"] = "online" if reply != "No response" else "offline"
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