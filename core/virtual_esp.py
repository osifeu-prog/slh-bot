import json
import sys
from pathlib import Path
import paho.mqtt.client as mqtt

BROKER = "broker.hivemq.com"
PORT = 1883
DEVICES_PATH = Path("state/devices.json")

device_id = sys.argv[1] if len(sys.argv) > 1 else "DEV_ESP_NEW_1786177919"
topic = f"slh/device/{device_id}/progress"

def on_connect(client, userdata, flags, rc):
    client.subscribe(topic)
    print("SUBSCRIBED", topic, flush=True)

def on_message(client, userdata, msg):
    payload = msg.payload.decode()
    print("RX", msg.topic, payload, flush=True)

    try:
        data = json.loads(DEVICES_PATH.read_text(encoding="utf-8"))
        devices = data.setdefault("devices", {})
        dev = devices.setdefault(device_id, {})
        dev["status"] = "online"
        dev["last_message"] = payload
        DEVICES_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print("DEVICE_UPDATED", device_id, "online", flush=True)
    except Exception as e:
        print("UPDATE_ERR", e, flush=True)

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.connect(BROKER, PORT, 60)
client.loop_forever()
