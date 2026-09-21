import unittest
from unittest.mock import patch


class MQTTBrokerProbeTests(unittest.TestCase):
    def setUp(self):
        from core.identity import OWNER_TELEGRAM_ID
        from slh_mcp.auth import Principal
        self.owner = Principal(
            subject=str(OWNER_TELEGRAM_ID),
            role="OWNER",
            permissions=frozenset(),
        )

    def test_probe_does_not_write_state(self):
        from slh_mcp.tools.mqtt import mqtt_probe

        class FakeClient:
            def __init__(self):
                self.connected = False
                self.disconnected = False

            def connect(self, broker, port, keepalive):
                self.connected = True
                return 0

            def disconnect(self):
                self.disconnected = True

            def username_pw_set(self, user, password):
                raise AssertionError("probe fixture should not need credentials")

        fake = FakeClient()
        with patch("slh_mcp.tools.mqtt.mqtt.Client", return_value=fake):
            result = mqtt_probe(self.owner)

        self.assertTrue(result["reachable"])
        self.assertTrue(result["connect_rc"] == 0)
        self.assertTrue(fake.connected)
        self.assertTrue(fake.disconnected)
        self.assertNotIn("password", repr(result).lower())

    def test_probe_sanitizes_connection_error(self):
        from slh_mcp.tools.mqtt import mqtt_probe

        class FakeClient:
            def connect(self, broker, port, keepalive):
                raise RuntimeError("password=secret should never escape")

            def disconnect(self):
                pass

        with patch("slh_mcp.tools.mqtt.mqtt.Client", return_value=FakeClient()):
            result = mqtt_probe(self.owner)

        self.assertFalse(result["reachable"])
        self.assertEqual(result["error"], "RuntimeError")
        self.assertNotIn("secret", repr(result))


if __name__ == "__main__":
    unittest.main()
