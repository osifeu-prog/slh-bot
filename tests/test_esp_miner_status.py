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


def test_build_miner_payload_returns_stored_metrics_and_safe_defaults():
    devices = {
        "ESP_TEST": {
            "miner": {
                "hashrate_ths": "12.5",
                "hashrate_24h": 11,
                "temperature": "67.2",
                "rejected_pct": "0.4",
                "status": "online",
                "pool": "pool.example",
                "worker": "worker-1",
                "daily_revenue_btc": "0.00012",
            }
        }
    }

    with patch("handlers.esp_control._load_devices", return_value=devices):
        payload = esp_control.build_miner_payload("ESP_TEST")
        missing = esp_control.build_miner_payload("MISSING")

    assert payload["hashrate_ths"] == 12.5
    assert payload["hashrate_24h"] == 11.0
    assert payload["temperature"] == 67.2
    assert payload["rejected_pct"] == 0.4
    assert payload["status"] == "online"
    assert payload["pool"] == "pool.example"
    assert payload["worker"] == "worker-1"
    assert payload["daily_revenue_btc"] == 0.00012
    assert missing["hashrate_ths"] == 0.0
    assert missing["status"] == "unknown"
    assert missing["worker"] == "MISSING"


def test_build_miner_payload_handles_malformed_numeric_values():
    devices = {
        "ESP_TEST": {
            "miner": {
                "hashrate_ths": "not-a-number",
                "hashrate_24h": None,
                "temperature": "",
                "rejected_pct": "invalid",
                "daily_revenue_btc": {},
            }
        }
    }

    with patch("handlers.esp_control._load_devices", return_value=devices):
        payload = esp_control.build_miner_payload("ESP_TEST")

    assert payload["hashrate_ths"] == 0.0
    assert payload["hashrate_24h"] == 0.0
    assert payload["temperature"] == 0.0
    assert payload["rejected_pct"] == 0.0
    assert payload["daily_revenue_btc"] == 0.0


def test_miner_status_command_is_owner_checked_and_read_only():
    device_id = "ESP_TEST"
    devices = {
        device_id: {
            "owner": "12345",
            "miner": {"status": "online", "hashrate_ths": 10},
        }
    }
    bot = Mock()
    handlers = _capture_handlers(bot)
    message = SimpleNamespace(
        text=f"/esp_miner_status {device_id}",
        from_user=SimpleNamespace(id=12345),
    )

    with patch("handlers.esp_control._load_devices", return_value=devices), patch(
        "handlers.esp_control._send_cmd"
    ) as send_cmd:
        esp_control.register_sync(bot)
        handlers["esp_miner_status"](message)

    bot.reply_to.assert_called_once()
    rendered = bot.reply_to.call_args.args[1]
    assert device_id in rendered
    assert "not live miner telemetry" in rendered
    assert "No MQTT command sent" in rendered
    send_cmd.assert_not_called()


def test_miner_status_command_rejects_non_owner():
    device_id = "ESP_TEST"
    devices = {device_id: {"owner": "12345", "miner": {"hashrate_ths": 10}}}
    bot = Mock()
    handlers = _capture_handlers(bot)
    message = SimpleNamespace(
        text=f"/esp_miner_status {device_id}",
        from_user=SimpleNamespace(id=99999),
    )

    with patch("handlers.esp_control._load_devices", return_value=devices), patch(
        "handlers.esp_control._send_cmd"
    ) as send_cmd:
        esp_control.register_sync(bot)
        handlers["esp_miner_status"](message)

    bot.reply_to.assert_called_once_with(message, "Not your device")
    send_cmd.assert_not_called()


def test_miner_status_command_requires_device_id():
    bot = Mock()
    handlers = _capture_handlers(bot)
    message = SimpleNamespace(
        text="/esp_miner_status",
        from_user=SimpleNamespace(id=12345),
    )

    esp_control.register_sync(bot)
    handlers["esp_miner_status"](message)

    bot.reply_to.assert_called_once_with(message, "Usage: /esp_miner_status <device_id>")
