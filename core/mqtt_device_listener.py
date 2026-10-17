"""Authenticated MQTT device heartbeat listener for SLH OS.

Legacy signed heartbeats remain supported. Local diagnostics require a distinct
HMAC v2 signature over the complete canonical payload, a fresh timestamp, a
known PC device ID, and a strict allow-listed schema. No logs or secrets are
accepted or persisted.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import socket
import time
from datetime import datetime, timezone
from typing import Any

import paho.mqtt.client as mqtt

from state_manager import atomic_json_update
from core.mqtt_config import BROKER, PORT, apply


TOPIC_ROOT = (os.getenv("MQTT_TOPIC_ROOT", "slh/device").strip("/") or "slh/device")
HEARTBEAT_TOPIC = f"{TOPIC_ROOT}/+/heartbeat"
HEARTBEAT_SECRET = os.getenv("MQTT_DEVICE_HEARTBEAT_SECRET", "").strip()
MAX_HEARTBEAT_SKEW_SECONDS = int(os.getenv("MQTT_HEARTBEAT_MAX_SKEW_SECONDS", "180"))

LOCAL_DIAGNOSTIC_DEVICE_IDS = frozenset({"PC_Osif2", "PC_MAIN_001"})
_DIAG_STATUSES = frozenset({"UP", "DOWN", "UNKNOWN"})
_BOT_STATUSES = frozenset({"UP", "RESTARTING", "EXITED", "UNKNOWN"})
_CONTAINER_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}")
_BRANCH_RE = re.compile(r"[A-Za-z0-9._/-]{1,80}")
_COMMIT_RE = re.compile(r"[0-9a-fA-F]{7,40}")


def _client_id() -> str:
    configured = str(os.getenv("MQTT_CLIENT_ID", "")).strip()
    if configured:
        return configured[:128]
    host = socket.gethostname().replace("/", "-").replace(" ", "-")
    return f"slh-device-listener-{host}-{os.getpid()}"[:128]


def _expected_signature(device_id: str, timestamp: float) -> str:
    """Backward-compatible HMAC for presence-only heartbeats."""
    message = f"{device_id}:{timestamp:.3f}".encode("utf-8")
    return hmac.new(
        HEARTBEAT_SECRET.encode("utf-8"),
        message,
        hashlib.sha256,
    ).hexdigest()


def _bounded_int(value: Any, minimum: int, maximum: int) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if value < minimum or value > maximum:
        return None
    return value


def sanitize_local_diagnostics(value: Any) -> dict[str, Any] | None:
    """Validate and return a small allow-listed diagnostic snapshot."""
    if not isinstance(value, dict) or set(value) != {
        "version", "docker", "postgres", "redis", "git", "compose", "bots"
    }:
        return None
    if value.get("version") != 1 or isinstance(value.get("version"), bool):
        return None

    docker = value.get("docker")
    if not isinstance(docker, dict) or set(docker) != {
        "daemon", "container_count", "running_count", "restarting_names"
    }:
        return None
    daemon = docker.get("daemon")
    total = _bounded_int(docker.get("container_count"), 0, 1000)
    running = _bounded_int(docker.get("running_count"), 0, 1000)
    restarting = docker.get("restarting_names")
    if not isinstance(daemon, str) or daemon not in _DIAG_STATUSES:
        return None
    if total is None or running is None or running > total:
        return None
    if not isinstance(restarting, list) or len(restarting) > 30:
        return None
    safe_restarting = []
    for name in restarting:
        if not isinstance(name, str) or not _CONTAINER_NAME_RE.fullmatch(name):
            return None
        safe_restarting.append(name)

    postgres = value.get("postgres")
    redis = value.get("redis")
    if not isinstance(postgres, str) or postgres not in _DIAG_STATUSES:
        return None
    if not isinstance(redis, str) or redis not in _DIAG_STATUSES:
        return None

    git = value.get("git")
    if not isinstance(git, dict) or set(git) != {"branch", "commit", "dirty", "dirty_files"}:
        return None
    branch = git.get("branch")
    commit = git.get("commit")
    dirty = git.get("dirty")
    dirty_files = _bounded_int(git.get("dirty_files"), 0, 100000)
    if not isinstance(branch, str) or not (
        branch == "UNKNOWN" or _BRANCH_RE.fullmatch(branch)
    ):
        return None
    if not isinstance(commit, str) or not (
        commit == "UNKNOWN" or _COMMIT_RE.fullmatch(commit)
    ):
        return None
    if not isinstance(dirty, bool) or dirty_files is None:
        return None

    compose = value.get("compose")
    if not isinstance(compose, dict) or set(compose) != {
        "utf8", "bad_byte_97_count", "root_env_present", "claude_env_present"
    }:
        return None
    utf8 = compose.get("utf8")
    bad_byte_count = _bounded_int(compose.get("bad_byte_97_count"), 0, 1000000)
    root_env = compose.get("root_env_present")
    claude_env = compose.get("claude_env_present")
    if not isinstance(utf8, str) or utf8 not in {"PASS", "FAIL", "UNKNOWN"} or bad_byte_count is None:
        return None
    if not isinstance(root_env, bool) or not isinstance(claude_env, bool):
        return None

    bots = value.get("bots")
    expected_bots = {"slh-ton-mnh", "slh-nifti", "slh-crazy-panel"}
    if not isinstance(bots, dict) or set(bots) != expected_bots:
        return None
    if any(not isinstance(status, str) or status not in _BOT_STATUSES
           for status in bots.values()):
        return None

    return {
        "version": 1,
        "docker": {
            "daemon": daemon,
            "container_count": total,
            "running_count": running,
            "restarting_names": safe_restarting,
        },
        "postgres": postgres,
        "redis": redis,
        "git": {
            "branch": branch,
            "commit": commit.lower() if commit != "UNKNOWN" else commit,
            "dirty": dirty,
            "dirty_files": dirty_files,
        },
        "compose": {
            "utf8": utf8,
            "bad_byte_97_count": bad_byte_count,
            "root_env_present": root_env,
            "claude_env_present": claude_env,
        },
        "bots": dict(bots),
    }


def _expected_diagnostics_signature(payload: dict[str, Any]) -> str:
    """HMAC v2 authenticates the entire payload, not just device ID/time."""
    unsigned = {key: value for key, value in payload.items() if key != "sig_v2"}
    device_id = str(unsigned.get("device_id") or "")
    timestamp = float(unsigned["ts"])
    canonical = json.dumps(
        unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )
    message = f"{device_id}:{timestamp:.3f}:".encode("utf-8") + canonical.encode("utf-8")
    return hmac.new(
        HEARTBEAT_SECRET.encode("utf-8"), message, hashlib.sha256
    ).hexdigest()


def _validated_diagnostics_payload(
    device_id: str, payload: dict[str, Any]
) -> dict[str, Any] | None:
    if not HEARTBEAT_SECRET or device_id not in LOCAL_DIAGNOSTIC_DEVICE_IDS:
        return None
    if set(payload) != {"device_id", "ts", "diagnostics", "sig_v2"}:
        return None
    if payload.get("device_id") != device_id:
        return None
    timestamp_value = payload.get("ts")
    if isinstance(timestamp_value, bool) or not isinstance(timestamp_value, (int, float)):
        return None
    timestamp = float(timestamp_value)
    if abs(time.time() - timestamp) > MAX_HEARTBEAT_SKEW_SECONDS:
        return None
    signature = str(payload.get("sig_v2") or "").strip().lower()
    try:
        expected = _expected_diagnostics_signature(payload)
    except (KeyError, TypeError, ValueError, OverflowError):
        return None
    if not signature or not hmac.compare_digest(signature, expected):
        return None
    return sanitize_local_diagnostics(payload.get("diagnostics"))


def _valid_heartbeat(device_id: str, payload: dict) -> bool:
    if not HEARTBEAT_SECRET:
        return False

    # A diagnostics-bearing message must use HMAC v2 over every field. A legacy
    # signature cannot be reused to smuggle in unsigned diagnostics.
    if "diagnostics" in payload or "sig_v2" in payload:
        return _validated_diagnostics_payload(device_id, payload) is not None

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

    diagnostics = None
    if isinstance(payload, dict) and ("diagnostics" in payload or "sig_v2" in payload):
        diagnostics = _validated_diagnostics_payload(device_id, payload)
        valid = diagnostics is not None
    else:
        valid = isinstance(payload, dict) and _valid_heartbeat(device_id, payload)

    if not valid:
        print(f"MQTT DEVICE HEARTBEAT REJECTED {device_id}: auth/schema", flush=True)
        return

    timestamp = datetime.now(timezone.utc).isoformat()

    def mutate(data):
        devices = data.setdefault("devices", {})
        dev = devices.setdefault(device_id, {})
        dev["status"] = "online"
        dev["last_heartbeat"] = timestamp
        if diagnostics is not None:
            # Timestamp diagnostic freshness from the signed source clock, not
            # receipt time, so replaying an old signed message cannot freshen it.
            source_timestamp = float(payload["ts"])
            dev["diagnostics"] = diagnostics
            dev["diagnostics_received_at"] = datetime.fromtimestamp(
                source_timestamp, timezone.utc
            ).isoformat()
        return True

    try:
        atomic_json_update(
            "devices.json",
            mutate,
            default={"devices": {}},
        )
        print(f"ONLINE {device_id}" + (" diagnostics=accepted" if diagnostics is not None else ""), flush=True)
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
