import copy
import unittest
from unittest.mock import patch

from core import agent_registry as registry


def _db():
    return {
        "users": {"owner": {"wallet": {"credits": 0.0}}},
        "agents": {
            "16": {
                "id": "16",
                "name": "Existing",
                "state": "idle",
                "role": "agent",
                "owner_id": "owner",
                "runtime_class": "EchoAgent",
                "inbox": [],
                "outbox": [],
            },
        },
    }


class AgentRegistryAtomicWriteTests(unittest.TestCase):
    def setUp(self):
        self.db = _db()

    def _atomic_update(self, mutate):
        return mutate(self.db)

    def _patches(self):
        return (
            patch.object(
                registry.state_manager,
                "atomic_update",
                side_effect=self._atomic_update,
            ),
            patch.object(registry.STORE, "rebuild_snapshot"),
            patch.object(registry.STORE, "_atomic_write") as direct_write,
            patch.object(registry, "log_event"),
        )

    def test_create_agent_mutates_through_shared_atomic_update(self):
        atomic, snapshot, direct_write, event = self._patches()
        with atomic, snapshot, direct_write, event, patch.object(
            registry, "can_create_agent", return_value=True
        ):
            agent_id, agent = registry.create_agent(
                "New Agent", owner_id="owner", runtime_class="EchoAgent"
            )

        self.assertEqual(agent_id, "17")
        self.assertEqual(self.db["agents"]["17"]["name"], "New Agent")
        self.assertEqual(agent["runtime_class"], "EchoAgent")
        direct_write.assert_not_called()

    def test_existing_agent_runtime_class_repair_is_atomic(self):
        del self.db["agents"]["16"]["runtime_class"]
        atomic, snapshot, direct_write, event = self._patches()
        with atomic, snapshot, direct_write, event:
            agent_id, agent = registry.create_agent(
                "Existing", owner_id="owner", runtime_class="EchoAgent"
            )

        self.assertEqual(agent_id, "16")
        self.assertEqual(agent["runtime_class"], "EchoAgent")
        self.assertEqual(
            self.db["agents"]["16"]["runtime_class"], "EchoAgent"
        )
        direct_write.assert_not_called()

    def test_update_agent_resolves_name_inside_atomic_mutation(self):
        atomic, snapshot, direct_write, event = self._patches()
        with atomic, snapshot, direct_write, event:
            agent_id, agent = registry.update_agent("Existing", state="active")

        self.assertEqual(agent_id, "16")
        self.assertEqual(agent["state"], "active")
        self.assertEqual(self.db["agents"]["16"]["state"], "active")
        direct_write.assert_not_called()

    def test_delete_agent_returns_handler_contract_and_is_atomic(self):
        atomic, snapshot, direct_write, event = self._patches()
        with atomic, snapshot, direct_write, event:
            agent_id, deleted = registry.delete_agent("16")

        self.assertEqual(agent_id, "16")
        self.assertEqual(deleted["name"], "Existing")
        self.assertNotIn("16", self.db["agents"])
        direct_write.assert_not_called()

    def test_send_message_preserves_structured_worker_task_atomically(self):
        task = {
            "command": "ask",
            "prompt": "Summarize verified progress",
            "uid": "owner",
        }
        expected = copy.deepcopy(task)
        atomic, snapshot, direct_write, event = self._patches()
        with atomic, snapshot, direct_write, event:
            agent_id = registry.send_message("Existing", task)

        self.assertEqual(agent_id, "16")
        self.assertEqual(self.db["agents"]["16"]["inbox"], [expected])
        direct_write.assert_not_called()

    def test_send_message_keeps_legacy_text_messages_compatible(self):
        atomic, snapshot, direct_write, event = self._patches()
        with atomic, snapshot, direct_write, event:
            agent_id = registry.send_message("16", "status")

        self.assertEqual(agent_id, "16")
        self.assertEqual(self.db["agents"]["16"]["inbox"], ["status"])
        direct_write.assert_not_called()

    def test_structured_messages_require_a_command(self):
        atomic, snapshot, direct_write, event = self._patches()
        with atomic, snapshot, direct_write, event:
            with self.assertRaisesRegex(ValueError, "INVALID_AGENT_MESSAGE"):
                registry.send_message("Existing", {"prompt": "missing command"})

        self.assertEqual(self.db["agents"]["16"]["inbox"], [])
        direct_write.assert_not_called()


if __name__ == "__main__":
    unittest.main()
