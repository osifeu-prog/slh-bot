import importlib.util
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from core import mqtt_device_listener as listener


REPORTER_PATH = Path(__file__).resolve().parents[1] / "tools" / "slh_local_diagnostics_reporter.py"
SPEC = importlib.util.spec_from_file_location("slh_local_diagnostics_reporter_test", REPORTER_PATH)
REPORTER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REPORTER)

SECRET = "test-mqtt-secret-with-32-characters-or-more"


def sample_diagnostics():
    return {
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


class LocalDiagnosticsProtocolTests(unittest.TestCase):
    def setUp(self):
        self.secret_patch = patch.object(listener, "HEARTBEAT_SECRET", SECRET)
        self.skew_patch = patch.object(listener, "MAX_HEARTBEAT_SKEW_SECONDS", 300)
        self.secret_patch.start()
        self.skew_patch.start()
        self.addCleanup(self.secret_patch.stop)
        self.addCleanup(self.skew_patch.stop)

    def test_reporter_payload_is_accepted_by_mqtt_listener(self):
        timestamp = round(time.time(), 3)
        payload = REPORTER.signed_payload("PC_Osif2", sample_diagnostics(), SECRET, timestamp)
        cleaned = listener._validated_diagnostics_payload("PC_Osif2", payload)
        self.assertEqual(cleaned, listener.sanitize_local_diagnostics(sample_diagnostics()))
        self.assertEqual(cleaned["docker"]["container_count"], 22)

    def test_signature_covers_entire_diagnostics_payload(self):
        payload = REPORTER.signed_payload("PC_Osif2", sample_diagnostics(), SECRET)
        payload["diagnostics"]["docker"]["daemon"] = "DOWN"
        self.assertIsNone(listener._validated_diagnostics_payload("PC_Osif2", payload))

    def test_schema_rejects_logs_secrets_unknown_fields_and_unbounded_values(self):
        diagnostics = sample_diagnostics()
        diagnostics["logs"] = "must never be accepted"
        self.assertIsNone(listener.sanitize_local_diagnostics(diagnostics))

        diagnostics = sample_diagnostics()
        diagnostics["docker"]["container_count"] = 1000000000
        self.assertIsNone(listener.sanitize_local_diagnostics(diagnostics))

        diagnostics = sample_diagnostics()
        diagnostics["git"]["branch"] = "main\nINJECTED"
        self.assertIsNone(listener.sanitize_local_diagnostics(diagnostics))

    def test_reporter_only_allows_fixed_device_ids_and_long_secret(self):
        with self.assertRaises(ValueError):
            REPORTER.signed_payload("UNREGISTERED_PC", sample_diagnostics(), SECRET)
        with self.assertRaises(ValueError):
            REPORTER.signed_payload("PC_Osif2", sample_diagnostics(), "too-short")

    def test_subprocess_invocation_disables_shell(self):
        with patch.object(REPORTER.subprocess, "run") as run:
            run.return_value.returncode = 0
            run.return_value.stdout = "OK"
            run.return_value.stderr = ""
            REPORTER._run(["docker", "info", "--format", "{{.ServerVersion}}"])
        self.assertIs(run.call_args.kwargs["shell"], False)


if __name__ == "__main__":
    unittest.main()
