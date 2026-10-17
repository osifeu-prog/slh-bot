import copy
import datetime
import threading
import unittest
from unittest.mock import patch

# The legacy module starts a daemon tutor worker at import time. Keep unit tests
# deterministic and prevent the background thread from touching any real state.
with patch.object(threading.Thread, "start", autospec=True):
    import internal_agent as agent


def _db():
    return {
        "users": {"u1": {"wallet": {"credits": 0.0}}},
        "agents": {
            "worker": {"inbox": [{"command": "whoami"}], "outbox": []},
        },
        "students": {
            "u1": {"points": 0, "completed_tasks": []},
        },
        "courses": {
            "bitcoin_mastery": {
                "tasks": {
                    "1": {"reward": 10},
                    "2": {
                        "reward": 20,
                        "validation": "file_exists:/definitely/not/a/real/slh-task-file",
                    },
                }
            }
        },
    }


class InternalAgentAtomicStateTests(unittest.TestCase):
    def _atomic_patch(self, db):
        return patch.object(
            agent.state_manager,
            "atomic_update",
            side_effect=lambda mutate: mutate(db),
        )

    def test_claim_and_finish_update_canonical_agent_state_atomically(self):
        db = _db()
        before = copy.deepcopy(db)

        with patch.object(agent.state_manager, "load_db", return_value=db), self._atomic_patch(db):
            claim = agent._claim_next_agent_message()

        self.assertIsNotNone(claim)
        self.assertEqual(claim["agent_name"], "worker")
        self.assertEqual(claim["message"]["command"], "whoami")
        self.assertEqual(db["agents"]["worker"]["inbox"], [])
        self.assertIn(claim["claim_id"], db["agents"]["worker"]["processing"])
        self.assertEqual(db["agents"]["worker"]["outbox"], [])
        self.assertNotEqual(db, before)

        with self._atomic_patch(db):
            saved = agent._finish_agent_message(
                claim["agent_name"], claim["claim_id"], "whoami result"
            )

        self.assertTrue(saved)
        self.assertEqual(db["agents"]["worker"]["processing"], {})
        self.assertEqual(db["agents"]["worker"]["outbox"], ["whoami result"])

    def test_expired_claim_is_requeued_and_can_be_claimed_again(self):
        db = _db()
        old_time = (
            datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(seconds=agent.CLAIM_TTL_SECONDS + 30)
        ).isoformat()
        db["agents"]["worker"]["inbox"] = []
        db["agents"]["worker"]["processing"] = {
            "abandoned-claim": {
                "message": {"command": "whoami"},
                "claimed_at": old_time,
            }
        }

        with patch.object(agent.state_manager, "load_db", return_value=db), self._atomic_patch(db):
            claim = agent._claim_next_agent_message()

        self.assertIsNotNone(claim)
        self.assertEqual(claim["message"]["command"], "whoami")
        self.assertNotEqual(claim["claim_id"], "abandoned-claim")
        self.assertNotIn("abandoned-claim", db["agents"]["worker"]["processing"])
        self.assertIn(claim["claim_id"], db["agents"]["worker"]["processing"])

    def test_task_completion_is_atomic_and_idempotent(self):
        db = _db()

        with self._atomic_patch(db):
            first = agent.complete_task("u1", "1")
        self.assertEqual(first, "✅ Task 1 completed! +10 points")
        self.assertEqual(db["students"]["u1"]["points"], 10)
        self.assertEqual(db["students"]["u1"]["completed_tasks"], ["1"])

        with self._atomic_patch(db):
            second = agent.complete_task("u1", "1")
        self.assertEqual(second, "✅ Task 1 already completed")
        self.assertEqual(db["students"]["u1"]["points"], 10)
        self.assertEqual(db["students"]["u1"]["completed_tasks"], ["1"])

    def test_missing_file_validation_does_not_change_student_state(self):
        db = _db()
        db["students"]["u1"].pop("completed_tasks")
        before = copy.deepcopy(db)

        with self._atomic_patch(db):
            result = agent.complete_task("u1", "2")

        self.assertTrue(result.startswith("❌ File "))
        self.assertEqual(db, before)

    def test_legacy_module_no_longer_writes_root_db_json_directly(self):
        from pathlib import Path

        source = Path(agent.__file__).read_text(encoding="utf-8")
        self.assertNotIn('open("db.json", "w")', source)
        self.assertNotIn('open("db.json","w")', source)
        self.assertNotIn('json.dump(db, f', source)


if __name__ == "__main__":
    unittest.main()
