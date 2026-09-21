import os
import unittest
from unittest.mock import patch

from core.identity import OWNER_TELEGRAM_ID


class MCPMQTTTests(unittest.TestCase):
    def setUp(self):
        from slh_mcp.auth import Principal
        self.owner = Principal(
            subject=str(OWNER_TELEGRAM_ID),
            role="OWNER",
            permissions=frozenset(),
        )

    def test_status_returns_non_secret_configuration(self):
        from slh_mcp.tools.mqtt import mqtt_status

        values = {
            "MQTT_BROKER": "mqtt.example.invalid",
            "MQTT_PORT": "8883",
            "MQTT_TLS": "1",
            "MQTT_USER": "configured-user",
            "MQTT_PASSWORD": "secret",
            "MQTT_TOPIC_ROOT": "slh/device",
        }
        with patch.dict(os.environ, values, clear=False):
            result = mqtt_status(self.owner)

        self.assertEqual(result["broker"], "mqtt.example.invalid")
        self.assertEqual(result["port"], 8883)
        self.assertTrue(result["tls"])
        self.assertTrue(result["credentials_configured"])
        self.assertEqual(result["topic_root"], "slh/device")
        rendered = repr(result).lower()
        self.assertNotIn("secret", rendered)
        self.assertNotIn("password", rendered)

    def test_status_does_not_connect(self):
        from slh_mcp.tools.mqtt import mqtt_status

        with patch("slh_mcp.tools.mqtt_config.connect") as connect:
            result = mqtt_status(self.owner)
        connect.assert_not_called()
        self.assertIn("broker", result)


if __name__ == "__main__":
    unittest.main()
