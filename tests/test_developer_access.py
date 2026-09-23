import json
import tempfile
import unittest
from pathlib import Path


def seed_db(path, uid="100"):
    path.write_text(
        json.dumps(
            {
                "users": {
                    uid: {
                        "role": "student",
                        "academy": {
                            "courses": {
                                "bitcoin_mastery": {
                                    "stage": 0,
                                    "completed": [],
                                }
                            }
                        },
                    }
                }
            }
        ),
        encoding="utf-8",
    )


class DeveloperAccessTests(unittest.TestCase):
    def setUp(self):
        import state_manager

        self.state_manager = state_manager
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "db.json"
        seed_db(self.db_path)

        self.old_db_file = state_manager.DB_FILE
        self.old_lock_path = state_manager._LOCK_PATH
        state_manager.DB_FILE = str(self.db_path)
        state_manager._LOCK_PATH = str(self.db_path) + ".lock"

        from core import developer_access

        self.service = developer_access

    def tearDown(self):
        self.state_manager.DB_FILE = self.old_db_file
        self.state_manager._LOCK_PATH = self.old_lock_path
        self.tmp.cleanup()

    def _set_bitcoin_complete(self):
        data = self.state_manager.load_db()
        data["users"]["100"]["academy"]["courses"]["bitcoin_mastery"] = {
            "stage": 12,
            "completed": list(range(1, 13)),
        }
        self.state_manager.save_db(data)

    def test_bitcoin_mastery_is_required(self):
        result = self.service.prerequisite_status("100")
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "bitcoin_mastery_incomplete")

        self._set_bitcoin_complete()

        result = self.service.prerequisite_status("100")
        self.assertTrue(result["ok"])
        self.assertEqual(result["completed"], 12)
        self.assertEqual(result["required"], 12)

    def test_request_is_idempotent(self):
        self._set_bitcoin_complete()

        first = self.service.request_access("100")
        second = self.service.request_access("100")

        self.assertTrue(first["ok"])
        self.assertEqual(first["status"], "pending")
        self.assertTrue(second["ok"])
        self.assertEqual(second["status"], "pending")

        stored = self.state_manager.load_db()["developer_access_requests"]["100"]
        self.assertEqual(stored["status"], "pending")

    def test_approval_rechecks_course(self):
        self._set_bitcoin_complete()
        self.assertTrue(self.service.request_access("100")["ok"])

        data = self.state_manager.load_db()
        data["users"]["100"]["academy"]["courses"]["bitcoin_mastery"]["completed"] = []
        self.state_manager.save_db(data)

        result = self.service.approve_access("100", "8789977826")
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "bitcoin_mastery_incomplete")

    def test_approval_sets_role_after_prerequisite(self):
        self._set_bitcoin_complete()
        self.assertTrue(self.service.request_access("100")["ok"])

        result = self.service.approve_access("100", "8789977826")
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "approved")

        user = self.state_manager.load_db()["users"]["100"]
        self.assertEqual(user["role"], "developer")
        self.assertEqual(user["developer_access_status"], "active")
        self.assertIn("agents.view_all", user["permissions"])
        self.assertEqual(
            self.state_manager.load_db()["developer_access_requests"]["100"]["status"],
            "approved",
        )

    def test_non_owner_cannot_approve(self):
        self._set_bitcoin_complete()
        self.assertTrue(self.service.request_access("100")["ok"])

        result = self.service.approve_access("100", "200")
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "owner_only")

    def test_approval_requires_pending_request(self):
        self._set_bitcoin_complete()

        result = self.service.approve_access("100", "8789977826")
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "request_not_pending")


if __name__ == "__main__":
    unittest.main()
