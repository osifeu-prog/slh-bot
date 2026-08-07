import json, time
from datetime import datetime, timezone
import paho.mqtt.client as mqtt

MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
RESPONSES = {}

def on_message(client, userdata, msg):
    RESPONSES[msg.topic] = msg.payload.decode()

mqtt_client = mqtt.Client()
mqtt_client.on_message = on_message
mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
mqtt_client.subscribe("slh/esp/response/#")
mqtt_client.loop_start()

def load_devices():
    try:
        with open("state/devices.json","r") as f:
            return json.load(f).get("devices",{})
    except:
        return {}

def save_devices(devices):
    with open("state/devices.json","r") as f:
        data = json.load(f)
    data["devices"] = devices
    with open("state/devices.json","w") as f:
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
        mqtt_client.publish(topic + "/command", "ping")
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
        lines = [f"{did}: {d.get('status','?')} | last: {d.get('last_heartbeat','never')}" for did, d in devices.items()]
        bot.reply_to(msg, "\n".join(lines))


