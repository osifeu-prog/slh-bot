"""Security regression tests for ESP wallet sync MQTT gating."""
import pytest

from core import mqtt_config


def test_wallet_sync_disabled_by_default(monkeypatch):
    monkeypatch.delenv("MQTT_WALLET_SYNC_ENABLED", raising=False)
    monkeypatch.delenv("MQTT_WALLET_SYNC_ALLOWED_BROKERS", raising=False)
    monkeypatch.setattr(mqtt_config, "BROKER", "private.example.invalid")
    monkeypatch.setattr(mqtt_config, "USER", "device-user")
    monkeypatch.setattr(mqtt_config, "PASSWORD", "test-password")
    monkeypatch.setattr(mqtt_config, "USE_TLS", True)
    assert mqtt_config.wallet_sync_security_ready() is False


@pytest.mark.parametrize(
    "broker,user,password,use_tls,enabled,allowlist",
    [
        ("broker.hivemq.com", "u", "p", True, "1", "broker.hivemq.com"),
        ("public.example.com", "u", "p", True, "1", ""),
        ("public.example.com", "u", "p", True, "1", "other.example.com"),
        ("private.example.invalid", "", "p", True, "1", "private.example.invalid"),
        ("private.example.invalid", "u", "", True, "1", "private.example.invalid"),
        ("private.example.invalid", "u", "p", False, "1", "private.example.invalid"),
        ("private.example.invalid", "u", "p", True, "0", "private.example.invalid"),
    ],
)
def test_wallet_sync_requires_all_security_controls(
    monkeypatch, broker, user, password, use_tls, enabled, allowlist
):
    monkeypatch.setenv("MQTT_WALLET_SYNC_ENABLED", enabled)
    monkeypatch.setenv("MQTT_WALLET_SYNC_ALLOWED_BROKERS", allowlist)
    monkeypatch.setattr(mqtt_config, "BROKER", broker)
    monkeypatch.setattr(mqtt_config, "USER", user)
    monkeypatch.setattr(mqtt_config, "PASSWORD", password)
    monkeypatch.setattr(mqtt_config, "USE_TLS", use_tls)
    assert mqtt_config.wallet_sync_security_ready() is False


def test_wallet_sync_allows_only_explicit_allowlisted_broker(monkeypatch):
    monkeypatch.setenv("MQTT_WALLET_SYNC_ENABLED", "1")
    monkeypatch.setenv(
        "MQTT_WALLET_SYNC_ALLOWED_BROKERS",
        "other.example.invalid, PRIVATE.EXAMPLE.INVALID.",
    )
    monkeypatch.setattr(mqtt_config, "BROKER", "private.example.invalid")
    monkeypatch.setattr(mqtt_config, "USER", "device-user")
    monkeypatch.setattr(mqtt_config, "PASSWORD", "test-password")
    monkeypatch.setattr(mqtt_config, "USE_TLS", True)
    assert mqtt_config.wallet_sync_security_ready() is True


def test_tls_setup_failure_raises(monkeypatch):
    class Client:
        def username_pw_set(self, username, password):
            self.credentials = (username, password)

        def tls_set(self):
            raise ValueError("simulated TLS failure")

    monkeypatch.setattr(mqtt_config, "USER", "device-user")
    monkeypatch.setattr(mqtt_config, "PASSWORD", "test-password")
    monkeypatch.setattr(mqtt_config, "USE_TLS", True)
    with pytest.raises(RuntimeError, match="refusing connection"):
        mqtt_config.apply(Client())
