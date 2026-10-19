"""Read-only local SLH diagnostics reporter for a supervised PC agent.

This process only probes fixed Docker/Git/Compose status commands and sends a
strictly allow-listed, HMAC-signed snapshot over MQTT. It never accepts remote
commands and never reads or emits secret values or container logs.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import subprocess
import time
from pathlib import Path
from threading import Event
from typing import Any

import paho.mqtt.client as mqtt


ALLOWED_DEVICE_IDS = frozenset({"PC_Osif2", "PC_MAIN_001"})
KNOWN_BOTS = ("slh-ton-mnh", "slh-nifti", "slh-crazy-panel")
_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}")
_BRANCH_RE = re.compile(r"[A-Za-z0-9._/-]{1,80}")
_COMMIT_RE = re.compile(r"[0-9a-fA-F]{7,40}")


def _run(args: list[str], *, cwd: Path | None = None, timeout: int = 8):
    """Run one fixed argument vector. Shell execution is intentionally disabled."""
    try:
        result = subprocess.run(
            args, cwd=str(cwd) if cwd else None, capture_output=True,
            text=True, encoding="utf-8", errors="replace", timeout=timeout,
            shell=False, check=False,
        )
        return result.returncode, result.stdout[:12000], result.stderr[:1200]
    except (OSError, subprocess.TimeoutExpired):
        return None, "", ""


def _root() -> Path:
    configured = os.getenv("SLH_LOCAL_ROOT", "").strip()
    if configured:
        return Path(configured)
    if os.name == "nt":
        return Path(r"D:\SLH_ECOSYSTEM")
    return Path.cwd()


def collect_diagnostics(root: Path | None = None) -> dict[str, Any]:
    """Collect bounded state only; output contains no log lines or env values."""
    root = (root or _root()).resolve()

    daemon_rc, _daemon_out, _ = _run(["docker", "info", "--format", "{{.ServerVersion}}"])
    daemon = "UNKNOWN" if daemon_rc is None else ("UP" if daemon_rc == 0 else "DOWN")
    ps_rc, ps_out, _ = _run([
        "docker", "ps", "-a", "--format", "{{.Names}}\t{{.State}}\t{{.Status}}"
    ])

    container_states: dict[str, tuple[str, str]] = {}
    restarting_names: list[str] = []
    if ps_rc == 0:
        for line in ps_out.splitlines()[:1000]:
            parts = line.split("\t", 2)
            if len(parts) != 3:
                continue
            name, state, status_text = (part.strip() for part in parts)
            if not _NAME_RE.fullmatch(name):
                continue
            container_states[name] = (state.lower(), status_text.lower())
            if state.lower() == "restarting" and len(restarting_names) < 30:
                restarting_names.append(name)

    running_count = sum(1 for state, _status in container_states.values() if state == "running")
    docker = {
        "daemon": daemon,
        "container_count": len(container_states),
        "running_count": running_count,
        "restarting_names": restarting_names,
    }

    def probe_container(container: str, command: list[str], expected: str | None = None) -> str:
        state = container_states.get(container)
        if state is None:
            return "DOWN" if ps_rc == 0 else "UNKNOWN"
        if state[0] != "running":
            return "DOWN"
        rc, out, _ = _run(["docker", "exec", container, *command], timeout=6)
        if rc is None:
            return "UNKNOWN"
        if rc != 0:
            return "DOWN"
        if expected is not None and out.strip().upper() != expected:
            return "DOWN"
        return "UP"

    postgres = probe_container("slh-postgres", ["pg_isready"])
    redis = probe_container("slh-redis", ["redis-cli", "ping"], expected="PONG")

    branch_rc, branch_out, _ = _run(["git", "-C", str(root), "branch", "--show-current"])
    commit_rc, commit_out, _ = _run(["git", "-C", str(root), "rev-parse", "--short", "HEAD"])
    dirty_rc, dirty_out, _ = _run(["git", "-C", str(root), "status", "--short"])
    branch = branch_out.strip() if branch_rc == 0 else "UNKNOWN"
    commit = commit_out.strip() if commit_rc == 0 else "UNKNOWN"
    if branch != "UNKNOWN" and not _BRANCH_RE.fullmatch(branch):
        branch = "UNKNOWN"
    if commit != "UNKNOWN" and not _COMMIT_RE.fullmatch(commit):
        commit = "UNKNOWN"
    dirty_files = len(dirty_out.splitlines()) if dirty_rc == 0 else 0
    git = {
        "branch": branch,
        "commit": commit.lower() if commit != "UNKNOWN" else commit,
        "dirty": bool(dirty_files) if dirty_rc == 0 else False,
        "dirty_files": dirty_files,
    }

    compose_path = root / "docker-compose.yml"
    try:
        raw = compose_path.read_bytes()
        raw.decode("utf-8")
        utf8 = "PASS"
    except UnicodeDecodeError:
        raw = compose_path.read_bytes()
        utf8 = "FAIL"
    except OSError:
        raw = b""
        utf8 = "UNKNOWN"

    compose = {
        "utf8": utf8,
        "bad_byte_97_count": raw.count(bytes([0x97])),
        "root_env_present": (root / ".env").is_file(),
        "claude_env_present": (root / "slh-claude-bot" / ".env").is_file(),
    }

    bots = {}
    for name in KNOWN_BOTS:
        state = container_states.get(name)
        if state is None:
            bots[name] = "UNKNOWN"
        elif state[0] == "restarting":
            bots[name] = "RESTARTING"
        elif state[0] == "running":
            bots[name] = "UP"
        else:
            bots[name] = "EXITED"

    return {
        "version": 1,
        "docker": docker,
        "postgres": postgres,
        "redis": redis,
        "git": git,
        "compose": compose,
        "bots": bots,
    }


def signed_payload(device_id: str, diagnostics: dict[str, Any], secret: str, timestamp: float | None = None) -> dict[str, Any]:
    """Build the HMAC v2 payload accepted by core.mqtt_device_listener."""
    if device_id not in ALLOWED_DEVICE_IDS:
        raise ValueError("LOCAL_DEVICE_ID_NOT_ALLOWED")
    if not secret or len(secret) < 32:
        raise ValueError("MQTT_DEVICE_HEARTBEAT_SECRET_MISSING_OR_TOO_SHORT")
    body = {
        "device_id": device_id,
        "ts": round(time.time() if timestamp is None else timestamp, 3),
        "diagnostics": diagnostics,
    }
    canonical = json.dumps(
        body, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )
    message = f"{device_id}:{body['ts']:.3f}:".encode("utf-8") + canonical.encode("utf-8")
    body["sig_v2"] = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()
    return body


def publish_once(root: Path | None = None) -> None:
    device_id = os.getenv("SLH_LOCAL_DEVICE_ID", "PC_Osif2").strip()
    secret = os.getenv("MQTT_DEVICE_HEARTBEAT_SECRET", "").strip()
    diagnostics = collect_diagnostics(root)
    payload = signed_payload(device_id, diagnostics, secret)

    broker = os.getenv("MQTT_BROKER", "broker.hivemq.com").strip() or "broker.hivemq.com"
    port = int(os.getenv("MQTT_PORT", "1883"))
    user = os.getenv("MQTT_USER", "").strip()
    password = os.getenv("MQTT_PASSWORD", "")
    use_tls = os.getenv("MQTT_TLS", "0") == "1"
    topic_root = os.getenv("MQTT_TOPIC_ROOT", "slh/device").strip("/") or "slh/device"
    topic = f"{topic_root}/{device_id}/heartbeat"

    connected = Event()
    connect_result = {"ok": False}

    def on_connect(client, userdata, flags, rc, *extra):
        try:
            connect_result["ok"] = int(rc) == 0
        except (TypeError, ValueError):
            connect_result["ok"] = False
        connected.set()

    client = mqtt.Client(client_id=f"slh-local-{device_id}"[:23])
    client.on_connect = on_connect
    if user:
        client.username_pw_set(user, password)
    if use_tls:
        client.tls_set()

    try:
        client.connect(broker, port, keepalive=30)
        client.loop_start()
        if not connected.wait(8) or not connect_result["ok"]:
            raise RuntimeError("MQTT_CONNECT_FAILED")
        info = client.publish(
            topic,
            json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False),
            qos=1,
            retain=False,
        )
        info.wait_for_publish(timeout=8)
        if not info.is_published():
            raise RuntimeError("MQTT_PUBLISH_TIMEOUT")
    finally:
        try:
            client.disconnect()
        except Exception:
            pass
        try:
            client.loop_stop()
        except Exception:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish read-only SLH local diagnostics")
    parser.add_argument("--once", action="store_true", help="publish once instead of running continuously")
    args = parser.parse_args()
    try:
        interval = int(os.getenv("SLH_LOCAL_DIAGNOSTICS_INTERVAL_SECONDS", "30"))
    except ValueError:
        interval = 30
    interval = min(300, max(15, interval))

    while True:
        try:
            publish_once()
            print("LOCAL_DIAGNOSTICS_PUBLISHED", flush=True)
        except Exception as exc:
            # Never print a traceback, environment values, MQTT payload, or credentials.
            print(f"LOCAL_DIAGNOSTICS_FAILED:{type(exc).__name__}", flush=True)
        if args.once:
            return 0
        time.sleep(interval)


if __name__ == "__main__":
    raise SystemExit(main())
