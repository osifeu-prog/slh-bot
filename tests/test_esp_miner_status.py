from types import SimpleNamespace
from unittest.mock import Mock, patch

from handlers import esp_control


def _capture_handlers(bot):
    handlers = {}

    def decorator(**kwargs):
        def register(callback):
            for command in kwargs.get("commands", []):
                handlers[command] = callback
            return callback
        return register

    bot.message_handler.side_effect = decorator
    return handlers


def _device(owner="12345"):
    return {
        "ESP_TEST": {
            "type": "esp32",
            "owner": owner,
            "miner_enabled": True,
            "mqtt_topic": "slh/esp/ESP_TEST",
        }
    }


def test_build_miner_payload_does_not_invent_zero_values():
    with patch("core.miner_service.get_miner_telemetry", return_value=None):
        payload = esp_control.build_miner_payload("ESP_TEST")

    assert payload["status"] == "NO_DATA"
    assert payload["temperature_c"] is None
    assert payload["watts"] is None
    assert payload["source"] == "none"


def test_esp_miner_status_is_owner_checked_and_never_sends_mqtt():
    bot = Mock()
    handlers = _capture_handlers(bot)
    message = SimpleNamespace(
        text="/esp_miner_status ESP_TEST",
        from_user=SimpleNamespace(id=12345),
    )

    with patch("handlers.esp_control._load_devices", return_value=_device()), patch(
        "handlers.esp_control.build_miner_payload",
        return_value={
            "status": "NO_DATA",
            "temperature_c": None,
            "watts": None,
        },
    ), patch("handlers.esp_control._send_cmd") as send_cmd:
        esp_control.register_sync(bot)
        handlers["esp_miner_status"](message)

    bot.reply_to.assert_called_once()
    assert "no authenticated telemetry" in bot.reply_to.call_args.args[1]
    send_cmd.assert_not_called()


def test_miner_status_rejects_non_owner_without_reading_telemetry():
    bot = Mock()
    handlers = _capture_handlers(bot)
    message = SimpleNamespace(
        text="/miner_status ESP_TEST",
        from_user=SimpleNamespace(id=99999),
    )

    with patch("handlers.esp_control._load_devices", return_value=_device()), patch(
        "handlers.esp_control.build_miner_payload"
    ) as build_payload:
        esp_control.register_sync(bot)
        handlers["miner_status"](message)

    bot.reply_to.assert_called_once_with(message, "Not your device")
    build_payload.assert_not_called()


def test_miner_list_only_includes_nodes_owned_by_the_requester():
    bot = Mock()
    handlers = _capture_handlers(bot)
    devices = {
        "ESP_OWNED": {"type": "esp32", "owner": "12345", "miner_enabled": True},
        "ESP_OTHER": {"type": "esp32", "owner": "99999", "miner_enabled": True},
        "PC_OWNED": {"type": "pc", "owner": "12345"},
    }
    message = SimpleNamespace(
        text="/miner_list",
        from_user=SimpleNamespace(id=12345),
    )

    with patch("handlers.esp_control._load_devices", return_value=devices), patch(
        "handlers.esp_control.build_miner_payload",
        return_value={"status": "NO_DATA"},
    ) as build_payload:
        esp_control.register_sync(bot)
        handlers["miner_list"](message)

    build_payload.assert_called_once_with("ESP_OWNED")
    rendered = bot.reply_to.call_args.args[1]
    assert "ESP_OWNED" in rendered
    assert "ESP_OTHER" not in rendered
    assert "PC_OWNED" not in rendered



def test_miner_status_marks_old_measurements_stale():
    bot = Mock()
    handlers = _capture_handlers(bot)
    message = SimpleNamespace(
        text="/miner_status ESP_TEST",
        from_user=SimpleNamespace(id=12345),
    )
    stale_payload = {
        "status": "OK",
        "temperature_c": 68.5,
        "watts": 3250,
        "volts": 230,
        "amps": 14,
        "energy_kwh": 12,
        "reported_status": "OK",
        "alerts": [],
        "last_seen": "2020-01-01T00:00:00Z",
        "source": "esp32_authenticated_http",
        "stale": True,
    }

    with patch("handlers.esp_control._load_devices", return_value=_device()), patch(
        "handlers.esp_control.build_miner_payload", return_value=stale_payload
    ):
        esp_control.register_sync(bot)
        handlers["miner_status"](message)

    rendered = bot.reply_to.call_args.args[1]
    assert "Status: `STALE`" in rendered
    assert "TELEMETRY_STALE" in rendered
