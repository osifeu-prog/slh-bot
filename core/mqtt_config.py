"""Central MQTT settings. Backward compatible: defaults match previous hardcoded values."""
import os

BROKER = os.getenv("MQTT_BROKER", "broker.hivemq.com")
PORT = int(os.getenv("MQTT_PORT", "1883"))
USER = os.getenv("MQTT_USER") or ""
PASSWORD = os.getenv("MQTT_PASSWORD") or ""
USE_TLS = os.getenv("MQTT_TLS", "0") == "1"


def apply(client):
    """Attach credentials and TLS to a paho client before connect()."""
    if USER:
        client.username_pw_set(USER, PASSWORD)
    if USE_TLS:
        try:
            client.tls_set()
        except Exception as e:
            print("MQTT TLS setup failed:", e)
    return client


def connect(client, keepalive=60):
    apply(client)
    return client.connect(BROKER, PORT, keepalive)
