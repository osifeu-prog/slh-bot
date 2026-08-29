import json
import paho.mqtt.client as mqtt
from pathlib import Path
from datetime import datetime, timezone

BROKER = "broker.hivemq.com"
PORT = 1883
DEVICES_PATH = Path("state/devices.json")


def on_connect(client, userdata, flags, rc):
    client.subscribe("slh/device/+/heartbeat")
    print("LISTENING slh/device/+/heartbeat", flush=True)


def on_message(client, userdata, msg):
    parts = msg.topic.split("/")
    if len(parts) < 3:
        return

    device_id = parts[2]

    try:
        data = json.loads(DEVICES_PATH.read_text(encoding="utf-8"))
        devices = data.setdefault("devices", {})
        dev = devices.setdefault(device_id, {})
        dev["status"] = "online"
        dev["last_heartbeat"] = datetime.now(timezone.utc).isoformat()
        DEVICES_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print("ONLINE", device_id, flush=True)
    except Exception as e:
        print("ERR", e, flush=True)


client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.connect(BROKER, PORT, 60)
client.loop_forever()
