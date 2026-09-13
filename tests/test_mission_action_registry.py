import unittest

from core.mission_action_registry import (
    MissionActionRegistry,
    build_default_registry,
)


class MissionActionRegistryTests(unittest.TestCase):
    def test_unknown_action_is_blocked(self):
        registry = build_default_registry()
        result = registry.execute(
            "shell.exec",
            mission_id="m1",
            payload={},
            context={},
            idempotency_key="mission:m1:execution",
        )
        self.assertEqual(result.status, "blocked")
        self.assertFalse(result.verified)
        self.assertEqual(result.error, "unsupported_action")

    def test_registered_action_must_prove_success(self):
        registry = MissionActionRegistry()
        registry.register(
            "test.action",
            lambda **kwargs: {
                "verified": True,
                "evidence": {"changed": True},
            },
        )
        result = registry.execute(
            "test.action",
            mission_id="m1",
            payload={"value": 1},
            context={"trusted": True},
            idempotency_key="mission:m1:execution",
        )
        self.assertEqual(result.status, "success")
        self.assertTrue(result.verified)
        self.assertTrue(result.evidence["changed"])

    def test_registered_action_without_verification_is_blocked(self):
        registry = MissionActionRegistry()
        registry.register(
            "fake.success",
            lambda **kwargs: {"execution_status": "success"},
        )
        result = registry.execute(
            "fake.success",
            mission_id="m1",
            payload={},
            context={},
            idempotency_key="mission:m1:execution",
        )
        self.assertEqual(result.status, "blocked")
        self.assertFalse(result.verified)

    def test_duplicate_registration_is_rejected(self):
        registry = MissionActionRegistry()
        registry.register("test.action", lambda **kwargs: {"verified": True})
        with self.assertRaises(ValueError):
            registry.register("test.action", lambda **kwargs: {"verified": True})


if __name__ == "__main__":
    unittest.main()
