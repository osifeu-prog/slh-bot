import json
import time
from pathlib import Path
import paho.mqtt.client as mqtt

BROKER = "broker.hivemq.com"
PORT = 1883
DB_PATH = Path("state/db.json")
DEV_PATH = Path("state/devices.json")

def get_progress():
    db = json.loads(DB_PATH.read_text(encoding="utf-8"))
    tasks = db.get("tasks", {})
    overall = int(sum(t.get("progress", 0) for t in tasks.values()) / len(tasks)) if tasks else 0
    return {"overall": overall, "tasks": {k: v.get("progress", 0) for k, v in tasks.items()}}

def broadcast_progress():
    devices = json.loads(DEV_PATH.read_text(encoding="utf-8")).get("devices", {})
    esp_devices = [did for did, d in devices.items() if d.get("type") == "esp32"]

    if not esp_devices:
        return "אין ESP רשומים"

    payload = json.dumps(get_progress(), ensure_ascii=False)
    sent = []

    c = mqtt.Client()
    c.connect(BROKER, PORT, 60)
    c.loop_start()
    time.sleep(0.5)

    for did in esp_devices:
        topic = devices[did].get("mqtt_topics", {}).get("progress")
        if not topic:
            continue
        c.publish(topic, payload)
        sent.append(did)

    time.sleep(1)
    c.loop_stop()
    c.disconnect()
    return f"📊 נשלח ל־{len(sent)} ESPים\n{sent}"
