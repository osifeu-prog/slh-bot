from types import SimpleNamespace
from unittest.mock import Mock, patch

from handlers.esp_handler import register_esp_handler


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


def _device(device_id):
    return {
        device_id: {
            "type": "esp32",
            "owner_id": "another-user",
            "mqtt_topic": f"slh/esp/{device_id}",
            "status": "offline",
        }
    }


def test_system_owner_can_run_read_only_esp_ping_for_device_owned_by_other_user():
    device_id = "ESP32_SOSY_HARDWARE_01"
    bot = Mock()
    handlers = _capture_handlers(bot)
    client = Mock()

    def publish(topic, payload):
        client.on_message(client, None, SimpleNamespace(payload=b"pong"))

    client.publish.side_effect = publish
    client.loop_start.side_effect = lambda: client.on_connect(client, None, {}, 0)
    message = SimpleNamespace(
        text=f"/esp_ping {device_id}",
        from_user=SimpleNamespace(id=8789977826),
    )

    with patch("handlers.esp_handler.load_devices", return_value=_device(device_id)), patch(
        "handlers.esp_handler.is_owner", return_value=True
    ), patch("handlers.esp_handler.mqtt.Client", return_value=client), patch(
        "handlers.esp_handler.atomic_device_update", return_value=True
    ) as device_update, patch("handlers.esp_handler.time.sleep"):
        register_esp_handler(bot)
        handlers["esp_ping"](message)

    client.publish.assert_called_once_with(f"slh/esp/{device_id}/command", "ping")
    device_update.assert_called_once()
    bot.reply_to.assert_called_once_with(message, f"ESP32 {device_id}: pong")


def test_non_owner_cannot_ping_device_owned_by_another_user():
    device_id = "ESP32_SOSY_HARDWARE_01"
    bot = Mock()
    handlers = _capture_handlers(bot)
    message = SimpleNamespace(
        text=f"/esp_ping {device_id}",
        from_user=SimpleNamespace(id=224223270),
    )

    with patch("handlers.esp_handler.load_devices", return_value=_device(device_id)), patch(
        "handlers.esp_handler.is_owner", return_value=False
    ), patch("handlers.esp_handler.mqtt.Client") as mqtt_client:
        register_esp_handler(bot)
        handlers["esp_ping"](message)

    mqtt_client.assert_not_called()
    bot.reply_to.assert_called_once_with(message, "אין לך הרשאה למכשיר זה")
