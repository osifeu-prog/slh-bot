"""Safe MQTT broker configuration/status for the SLH Control Plane."""

from __future__ import annotations

import os

import paho.mqtt.client as mqtt

from core import mqtt_config


def _principal(principal=None):
    if principal is not None:
        return principal
    from slh_mcp.auth import current_principal
    value = current_principal()
    if value is None:
        raise PermissionError("MCP authentication required")
    return value


def mqtt_status(principal=None) -> dict:
    _principal(principal)
    broker = str(os.getenv("MQTT_BROKER", "broker.hivemq.com"))
    port = int(os.getenv("MQTT_PORT", "1883"))
    tls = os.getenv("MQTT_TLS", "0") == "1"
    user_configured = bool(str(os.getenv("MQTT_USER", "")).strip())
    password_configured = bool(str(os.getenv("MQTT_PASSWORD", "")).strip())
    topic_root = str(os.getenv("MQTT_TOPIC_ROOT", "slh/device").strip("/") or "slh/device")
    return {
        "broker": broker,
        "port": port,
        "tls": tls,
        "credentials_configured": user_configured and password_configured,
        "topic_root": topic_root,
        "listener_module": "core.mqtt_device_listener",
    }


def _tool_mqtt_status():
    return mqtt_status()

def mqtt_probe(principal=None) -> dict:
    _principal(principal)
    client = create_probe_client()
    try:
        rc = client.connect(mqtt_config.BROKER, mqtt_config.PORT, keepalive=10)
        return {
            "reachable": rc == 0,
            "connect_rc": int(rc),
            "broker": mqtt_config.BROKER,
            "port": mqtt_config.PORT,
            "tls": mqtt_config.USE_TLS,
        }
    except Exception as exc:
        return {
            "reachable": False,
            "broker": BROKER,
            "port": PORT,
            "tls": USE_TLS,
            "error": type(exc).__name__,
        }
    finally:
        try:
            client.disconnect()
        except Exception:
            pass


def create_probe_client():
    client = mqtt.Client(client_id="slh-mcp-probe")
    mqtt_config.apply(client)
    return client


def _tool_mqtt_probe():
    return mqtt_probe()