import json
import time
from pathlib import Path
import paho.mqtt.client as mqtt

MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883

DB_PATH = Path("state/db.json")
DEV_PATH = Path("state/devices.json")


def get_progress():
    db = json.loads(DB_PATH.read_text(encoding="utf-8"))
    tasks = db.get("tasks", {})
    overall = int(sum(t.get("progress", 0) for t in tasks.values()) / len(tasks)) if tasks else 0
    return {
        "overall": overall,
        "tasks": {k: v.get("progress", 0) for k, v in tasks.items()}
    }


def publish_progress(device_id):
    devices = json.loads(DEV_PATH.read_text(encoding="utf-8")).get("devices", {})
    dev = devices.get(device_id)
    if not dev:
        return False, "device not found"
    topic = dev.get("mqtt_topics", {}).get("progress")
    if not topic:
        return False, "progress topic missing"
    payload = json.dumps(get_progress(), ensure_ascii=False)

    client = mqtt.Client()
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_start()
    time.sleep(0.5)
    client.publish(topic, payload)
    time.sleep(1)
    client.loop_stop()
    client.disconnect()
    return True, payload
