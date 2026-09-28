import json
import time
import unittest
from unittest.mock import patch


class MQTTListenerTests(unittest.TestCase):
    def test_topic_root_is_configurable(self):
        with patch.dict("os.environ", {"MQTT_TOPIC_ROOT": "slh/v1/device"}, clear=False):
            import importlib
            import core.mqtt_device_listener as listener
            listener = importlib.reload(listener)
            self.assertEqual(listener.HEARTBEAT_TOPIC, "slh/v1/device/+/heartbeat")

    def test_heartbeat_update_uses_atomic_json_update(self):
        import core.mqtt_device_listener as listener

        payload = {"devices": {}}
        timestamp = time.time()
        listener.HEARTBEAT_SECRET = "test-secret"
        listener.MAX_HEARTBEAT_SKEW_SECONDS = 300
        heartbeat = {
            "ts": timestamp,
            "sig": listener._expected_signature("device-1", timestamp),
        }
        message = type(
            "Message",
            (),
            {
                "topic": "slh/device/device-1/heartbeat",
                "payload": json.dumps(heartbeat).encode("utf-8"),
            },
        )()

        with patch.object(listener, "atomic_json_update") as update:
            def apply(filename, mutate, default=None):
                data = dict(payload)
                mutate(data)
                self.assertEqual(data["devices"]["device-1"]["status"], "online")
                self.assertIn("last_heartbeat", data["devices"]["device-1"])
            update.side_effect = apply
            listener.on_message(None, None, message)
            update.assert_called_once()

    def test_module_import_has_no_connect_side_effect(self):
        with patch("paho.mqtt.client.Client.connect") as connect,              patch("paho.mqtt.client.Client.loop_forever") as loop:
            import importlib
            import core.mqtt_device_listener as listener
            importlib.reload(listener)
            connect.assert_not_called()
            loop.assert_not_called()


if __name__ == "__main__":
    unittest.main()
