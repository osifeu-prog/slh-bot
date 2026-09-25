"""Authenticated MQTT device heartbeat listener for SLH OS.

Importing this module is side-effect free. The broker connection starts only
when run_forever() or the __main__ entrypoint is invoked.

Heartbeat writes are accepted only with a shared HMAC secret and a fresh
timestamp. This prevents anonymous public-MQTT messages from being treated
as authoritative device presence.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import socket
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

from state_manager import atomic_json_update
from core.mqtt_config import BROKER, PORT, apply


TOPIC_ROOT = (os.getenv("MQTT_TOPIC_ROOT", "slh/device").strip("/") or "slh/device")
HEARTBEAT_TOPIC = f"{TOPIC_ROOT}/+/heartbeat"
HEARTBEAT_SECRET = os.getenv("MQTT_DEVICE_HEARTBEAT_SECRET", "").strip()
MAX_HEARTBEAT_SKEW_SECONDS = int(os.getenv("MQTT_HEARTBEAT_MAX_SKEW_SECONDS", "180"))


def _client_id() -> str:
    configured = str(os.getenv("MQTT_CLIENT_ID", "")).strip()
    if configured:
        return configured[:128]
    host = socket.gethostname().replace("/", "-").replace(" ", "-")
    return f"slh-device-listener-{host}-{os.getpid()}"[:128]


def _expected_signature(device_id: str, timestamp: float) -> str:
    message = f"{device_id}:{timestamp:.3f}".encode("utf-8")
    return hmac.new(
        HEARTBEAT_SECRET.encode("utf-8"),
        message,
        hashlib.sha256,
    ).hexdigest()


def _valid_heartbeat(device_id: str, payload: dict) -> bool:
    if not HEARTBEAT_SECRET:
        return False

    payload_device_id = str(payload.get("device_id", "")).strip()
    if payload_device_id and payload_device_id != device_id:
        return False

    try:
        timestamp = float(payload["ts"])
    except (KeyError, TypeError, ValueError):
        return False

    if abs(time.time() - timestamp) > MAX_HEARTBEAT_SKEW_SECONDS:
        return False

    signature = str(payload.get("sig", "")).strip().lower()
    expected = _expected_signature(device_id, timestamp)
    return bool(signature) and hmac.compare_digest(signature, expected)


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

    try:
        payload = json.loads(msg.payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        print(f"MQTT DEVICE HEARTBEAT REJECTED {device_id}: invalid json", flush=True)
        return

    if not isinstance(payload, dict) or not _valid_heartbeat(device_id, payload):
        print(f"MQTT DEVICE HEARTBEAT REJECTED {device_id}: auth", flush=True)
        return

    timestamp = datetime.now(timezone.utc).isoformat()

    def mutate(data):
        devices = data.setdefault("devices", {})
        dev = devices.setdefault(device_id, {})
        dev["status"] = "online"
        dev["last_heartbeat"] = timestamp
        return True

    try:
        atomic_json_update(
            "devices.json",
            mutate,
            default={"devices": {}},
        )
        print(f"ONLINE {device_id}", flush=True)
    except Exception as exc:
        print(
            f"MQTT DEVICE UPDATE ERROR: {type(exc).__name__}",
            flush=True,
        )


def create_client() -> mqtt.Client:
    client = mqtt.Client(client_id=_client_id())
    client.on_connect = on_connect
    client.on_message = on_message
    apply(client)
    return client


def run_forever() -> None:
    if not HEARTBEAT_SECRET:
        print(
            "MQTT DEVICE HEARTBEAT LISTENER DISABLED: "
            "MQTT_DEVICE_HEARTBEAT_SECRET is missing",
            flush=True,
        )
        return

    client = create_client()
    client.connect(BROKER, PORT, 60)
    client.loop_forever()


if __name__ == "__main__":
    run_forever()
