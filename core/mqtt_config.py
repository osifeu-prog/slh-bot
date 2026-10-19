"""Central MQTT settings. Backward compatible: defaults match previous hardcoded values."""
import os

BROKER = os.getenv("MQTT_BROKER", "broker.hivemq.com")
PORT = int(os.getenv("MQTT_PORT", "1883"))
USER = os.getenv("MQTT_USER") or ""
PASSWORD = os.getenv("MQTT_PASSWORD") or ""
USE_TLS = os.getenv("MQTT_TLS", "0") == "1"


def wallet_sync_security_ready():
    """Fail closed unless wallet sync has an explicitly approved secure MQTT setup.

    The enable flag acknowledges that broker-side per-device ACLs and identity
    binding have been configured. The broker must also appear in an explicit
    operator-maintained allowlist. This function never changes configuration
    or connects to a broker.
    """
    explicitly_enabled = os.getenv("MQTT_WALLET_SYNC_ENABLED", "0") == "1"
    configured_brokers = {
        item.strip().lower().rstrip(".")
        for item in os.getenv("MQTT_WALLET_SYNC_ALLOWED_BROKERS", "").split(",")
        if item.strip()
    }
    normalized_broker = str(BROKER or "").strip().lower().rstrip(".")
    # Never treat the public sample brokers as secure wallet-sync endpoints,
    # even if they were accidentally added to the allowlist.
    public_default_brokers = {
        "broker.hivemq.com",
        "test.mosquitto.org",
    }
    broker_is_approved = bool(
        normalized_broker
        and normalized_broker not in public_default_brokers
        and normalized_broker in configured_brokers
    )
    return bool(
        explicitly_enabled
        and broker_is_approved
        and USER
        and PASSWORD
        and USE_TLS
    )


def apply(client):
    """Attach credentials and TLS to a paho client before connect()."""
    if USER:
        client.username_pw_set(USER, PASSWORD)
    if USE_TLS:
        try:
            client.tls_set()
        except Exception as e:
            # Never continue with a plaintext client after TLS setup failed.
            raise RuntimeError("MQTT TLS setup failed; refusing connection") from e
    return client


def connect(client, keepalive=60):
    apply(client)
    return client.connect(BROKER, PORT, keepalive)
