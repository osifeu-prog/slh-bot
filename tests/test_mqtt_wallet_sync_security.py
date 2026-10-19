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
        ("test.mosquitto.org", "u", "p", True, "1", "test.mosquitto.org"),
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

def test_direct_esp_sync_command_is_blocked_before_wallet_read(monkeypatch):
    from handlers import esp_control

    monkeypatch.setattr(esp_control, "_load_devices", lambda: {"device-1": {"owner": "123"}})
    monkeypatch.setattr(esp_control, "build_sync_payload", lambda uid: pytest.fail("wallet payload must not be read"))
    monkeypatch.setattr(mqtt_config, "BROKER", "broker.hivemq.com")
    monkeypatch.setattr(mqtt_config, "USER", "device-user")
    monkeypatch.setattr(mqtt_config, "PASSWORD", "test-password")
    monkeypatch.setattr(mqtt_config, "USE_TLS", True)
    monkeypatch.delenv("MQTT_WALLET_SYNC_ENABLED", raising=False)
    monkeypatch.delenv("MQTT_WALLET_SYNC_ALLOWED_BROKERS", raising=False)

    registered = {}

    class FakeBot:
        def message_handler(self, commands):
            return lambda fn: registered.setdefault(commands[0], fn)

        def reply_to(self, message, text):
            self.reply = text

    bot = FakeBot()
    esp_control.register_sync(bot)

    class User:
        id = 123

    class Chat:
        id = 123

    class Message:
        text = "/esp_sync device-1"
        from_user = User()
        chat = Chat()

    registered["esp_sync"](Message())
    assert "disabled" in bot.reply.lower()

def test_esp_view_is_blocked_before_mqtt_request_when_wallet_sync_disabled(monkeypatch):
    from handlers import esp_control

    monkeypatch.setattr(esp_control, "_load_devices", lambda: {"device-1": {"owner": "123"}})
    monkeypatch.setattr(mqtt_config, "BROKER", "broker.hivemq.com")
    monkeypatch.setattr(mqtt_config, "USER", "device-user")
    monkeypatch.setattr(mqtt_config, "PASSWORD", "test-password")
    monkeypatch.setattr(mqtt_config, "USE_TLS", False)
    monkeypatch.delenv("MQTT_WALLET_SYNC_ENABLED", raising=False)
    monkeypatch.delenv("MQTT_WALLET_SYNC_ALLOWED_BROKERS", raising=False)
    monkeypatch.setattr(
        esp_control.mqtt,
        "Client",
        lambda: pytest.fail("screen response may contain wallet data; MQTT must not be used"),
    )

    registered = {}

    class FakeBot:
        def message_handler(self, commands):
            return lambda fn: registered.setdefault(commands[0], fn)

        def reply_to(self, message, text):
            self.reply = text

    bot = FakeBot()
    esp_control.register_screen(bot)

    class User:
        id = 123

    class Message:
        text = "/esp_view device-1"
        from_user = User()

    registered["esp_view"](Message())
    assert "disabled" in bot.reply.lower()


def test_mqtt_action_sync_is_blocked_before_wallet_read(monkeypatch):
    from handlers import esp_control

    monkeypatch.setattr(
        esp_control,
        "build_sync_payload",
        lambda uid: pytest.fail("wallet payload must not be read"),
    )
    monkeypatch.setattr(mqtt_config, "BROKER", "broker.hivemq.com")
    monkeypatch.setattr(mqtt_config, "USER", "device-user")
    monkeypatch.setattr(mqtt_config, "PASSWORD", "test-password")
    monkeypatch.setattr(mqtt_config, "USE_TLS", False)
    monkeypatch.delenv("MQTT_WALLET_SYNC_ENABLED", raising=False)
    monkeypatch.delenv("MQTT_WALLET_SYNC_ALLOWED_BROKERS", raising=False)

    class FakeBot:
        def send_message(self, uid, text, **kwargs):
            self.last_message = text

    bot = FakeBot()
    esp_control._handle_action(bot, "123", "device-1", "sync")
    assert "disabled" in bot.last_message.lower()

