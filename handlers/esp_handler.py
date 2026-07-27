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

def register_esp_handler(bot):
    @bot.message_handler(commands=["esp_ping"])
    def esp_ping(msg):
        parts = msg.text.split()
        device_id = parts[1] if len(parts) > 1 else "esp32_01"
        with open("state/db.json","r") as f:
            db = json.load(f)
        dev = db.get("devices",{}).get(device_id)
        if not dev:
            bot.reply_to(msg, f"Device {device_id} not found.")
            return
        topic = dev.get("mqtt_topic", f"slh/esp/{device_id}")
        mqtt_client.publish(topic + "/command", "ping")
        time.sleep(2)
        reply = RESPONSES.get(topic + "/response", "No response")
        dev["last_heartbeat"] = datetime.now(timezone.utc).isoformat()
        dev["status"] = "online" if reply!= "No response" else "offline"
        with open("state/db.json","w") as f:
            json.dump(db, f, indent=2)
        bot.reply_to(msg, f"ESP32 {device_id}: {reply}")

    @bot.message_handler(commands=["esp_status"])
    def esp_status(msg):
        with open("state/db.json","r") as f:
            db = json.load(f)
        devs = db.get("devices",{})
        if not devs:
            bot.reply_to(msg, "No devices registered.")
            return
        lines = [f"{did}: {d.get('status','?')} | last: {d.get('last_heartbeat','never')}" for did, d in dev


cd ~/slh_clean

# 1. סוגר את הקובץ כמו שצריך
cat >> handlers/esp_handler.py << 'EOF'
.items()]}
        bot.reply_to(msg, "\n".join(lines))
