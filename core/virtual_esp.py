import json
import sys
from pathlib import Path
import paho.mqtt.client as mqtt

from core.mqtt_config import BROKER as _MB
BROKER = _MB
from core.mqtt_config import PORT as _MP
PORT = _MP
DEVICES_PATH = Path("state/devices.json")

device_id = sys.argv[1] if len(sys.argv) > 1 else "DEV_ESP_NEW_1786177919"
def _progress_topic():
    try:
        data = json.loads(DEVICES_PATH.read_text(encoding="utf-8"))
        dev = data.get("devices", {}).get(device_id, {})
        topic = (dev.get("mqtt_topics") or {}).get("progress")
        if topic:
            return topic
    except Exception:
        pass
    return f"slh/esp/{device_id}/progress"


topic = _progress_topic()

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
__import__("core.mqtt_config",fromlist=["apply"]).apply(client)
client.connect(BROKER, PORT, 60)
client.loop_forever()
