"""Explicit MQTT device heartbeat listener for SLH OS.

Importing this module is side-effect free. The broker connection starts only
when run_forever() or the __main__ entrypoint is invoked.
"""

from __future__ import annotations

import os
import socket
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

import state_manager
from core.mqtt_config import BROKER, PORT, apply


TOPIC_ROOT = (os.getenv("MQTT_TOPIC_ROOT", "slh/device").strip("/") or "slh/device")
HEARTBEAT_TOPIC = f"{TOPIC_ROOT}/+/heartbeat"


def _client_id() -> str:
    configured = str(os.getenv("MQTT_CLIENT_ID", "")).strip()
    if configured:
        return configured[:128]
    host = socket.gethostname().replace("/", "-").replace(" ", "-")
    return f"slh-device-listener-{host}-{os.getpid()}"[:128]


def on_connect(client, userdata, flags, rc):
    if rc != 0:
        print(f"MQTT CONNECT FAILED rc={rc}", flush=True)
        return
    client.subscribe(HEARTBEAT_TOPIC)
    print(f"LISTENING {HEARTBEAT_TOPIC}", flush=True)


def on_message(client, userdata, msg):
    parts = str(msg.topic).split("/")
    prefix_parts = TOPIC_ROOT.split("/")
    if len(parts) != len(prefix_parts) + 2:
        return
    if parts[:len(prefix_parts)] != prefix_parts or parts[-1] != "heartbeat":
        return

    device_id = parts[-2]
    timestamp = datetime.now(timezone.utc).isoformat()

    def mutate(data):
        devices = data.setdefault("devices", {})
        dev = devices.setdefault(device_id, {})
        dev["status"] = "online"
        dev["last_heartbeat"] = timestamp
        return True

    try:
        state_manager.atomic_json_update(
            "devices.json",
            mutate,
            default={"devices": {}},
        )
        print(f"ONLINE {device_id}", flush=True)
    except Exception as exc:
        print(f"MQTT DEVICE UPDATE ERROR: {type(exc).__name__}", flush=True)


def create_client() -> mqtt.Client:
    client = mqtt.Client(client_id=_client_id())
    client.on_connect = on_connect
    client.on_message = on_message
    apply(client)
    return client


def run_forever() -> None:
    client = create_client()
    client.connect(BROKER, PORT, 60)
    client.loop_forever()


if __name__ == "__main__":
    run_forever()
