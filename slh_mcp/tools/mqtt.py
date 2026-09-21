"""Safe MQTT broker configuration/status for the SLH Control Plane."""

from __future__ import annotations

import os

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