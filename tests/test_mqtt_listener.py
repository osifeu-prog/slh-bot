import hashlib
import hmac
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

    def test_signed_v2_diagnostics_are_stored_as_allow_listed_snapshot(self):
        import core.mqtt_device_listener as listener

        listener.HEARTBEAT_SECRET = "test-secret-with-at-least-32-characters"
        listener.MAX_HEARTBEAT_SKEW_SECONDS = 300
        timestamp = round(time.time(), 3)
        diagnostics = {
            "version": 1,
            "docker": {
                "daemon": "UP",
                "container_count": 22,
                "running_count": 20,
                "restarting_names": ["slh-ton-mnh"],
            },
            "postgres": "UP",
            "redis": "UP",
            "git": {"branch": "main", "commit": "abcdef1", "dirty": True, "dirty_files": 3},
            "compose": {
                "utf8": "PASS",
                "bad_byte_97_count": 0,
                "root_env_present": True,
                "claude_env_present": False,
            },
            "bots": {
                "slh-ton-mnh": "RESTARTING",
                "slh-nifti": "UNKNOWN",
                "slh-crazy-panel": "UP",
            },
        }
        payload = {"device_id": "PC_Osif2", "ts": timestamp, "diagnostics": diagnostics}
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        signed = f"PC_Osif2:{timestamp:.3f}:".encode("utf-8") + canonical.encode("utf-8")
        payload["sig_v2"] = hmac.new(
            listener.HEARTBEAT_SECRET.encode("utf-8"), signed, hashlib.sha256
        ).hexdigest()
        message = type(
            "Message",
            (),
            {
                "topic": "slh/device/PC_Osif2/heartbeat",
                "payload": json.dumps(payload).encode("utf-8"),
            },
        )()

        with patch.object(listener, "atomic_json_update") as update:
            def apply(filename, mutate, default=None):
                data = {"devices": {}}
                mutate(data)
                record = data["devices"]["PC_Osif2"]
                self.assertEqual(record["status"], "online")
                self.assertEqual(record["diagnostics"]["docker"]["container_count"], 22)
                self.assertNotIn("logs", record["diagnostics"])
                self.assertIn("diagnostics_received_at", record)
            update.side_effect = apply
            listener.on_message(None, None, message)
            update.assert_called_once()

    def test_legacy_signature_cannot_authenticate_diagnostics(self):
        import core.mqtt_device_listener as listener

        listener.HEARTBEAT_SECRET = "test-secret"
        listener.MAX_HEARTBEAT_SKEW_SECONDS = 300
        timestamp = time.time()
        diagnostics = {"version": 1}
        payload = {
            "device_id": "PC_Osif2",
            "ts": timestamp,
            "diagnostics": diagnostics,
            "sig": listener._expected_signature("PC_Osif2", timestamp),
        }
        message = type(
            "Message",
            (),
            {
                "topic": "slh/device/PC_Osif2/heartbeat",
                "payload": json.dumps(payload).encode("utf-8"),
            },
        )()

        with patch.object(listener, "atomic_json_update") as update:
            listener.on_message(None, None, message)
            update.assert_not_called()

    def test_diagnostics_signature_does_not_allow_payload_tampering(self):
        import core.mqtt_device_listener as listener

        listener.HEARTBEAT_SECRET = "test-secret-with-at-least-32-characters"
        listener.MAX_HEARTBEAT_SKEW_SECONDS = 300
        timestamp = round(time.time(), 3)
        diagnostics = {
            "version": 1,
            "docker": {
                "daemon": "UP", "container_count": 1, "running_count": 1,
                "restarting_names": [],
            },
            "postgres": "UP",
            "redis": "UP",
            "git": {"branch": "main", "commit": "abcdef1", "dirty": False, "dirty_files": 0},
            "compose": {
                "utf8": "PASS", "bad_byte_97_count": 0,
                "root_env_present": True, "claude_env_present": True,
            },
            "bots": {
                "slh-ton-mnh": "UP", "slh-nifti": "UP", "slh-crazy-panel": "UP",
            },
        }
        payload = {"device_id": "PC_Osif2", "ts": timestamp, "diagnostics": diagnostics}
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        signed = f"PC_Osif2:{timestamp:.3f}:".encode("utf-8") + canonical.encode("utf-8")
        payload["sig_v2"] = hmac.new(
            listener.HEARTBEAT_SECRET.encode("utf-8"), signed, hashlib.sha256
        ).hexdigest()
        payload["diagnostics"]["docker"]["daemon"] = "DOWN"
        message = type(
            "Message",
            (),
            {
                "topic": "slh/device/PC_Osif2/heartbeat",
                "payload": json.dumps(payload).encode("utf-8"),
            },
        )()

        with patch.object(listener, "atomic_json_update") as update:
            listener.on_message(None, None, message)
            update.assert_not_called()

    def test_module_import_has_no_connect_side_effect(self):
        with patch("paho.mqtt.client.Client.connect") as connect,              patch("paho.mqtt.client.Client.loop_forever") as loop:
            import importlib
            import core.mqtt_device_listener as listener
            importlib.reload(listener)
            connect.assert_not_called()
            loop.assert_not_called()


if __name__ == "__main__":
    unittest.main()
