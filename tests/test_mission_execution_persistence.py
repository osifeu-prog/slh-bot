import json
import tempfile
import unittest
from pathlib import Path

from core.mission_execution_persistence import persist_verified_execution


class MissionExecutionPersistenceTests(unittest.TestCase):
    def _root(self):
        root = Path(tempfile.mkdtemp())
        path = root / "state" / "missions"
        path.mkdir(parents=True)
        (path / "board.json").write_text(
            json.dumps({
                "missions": [{
                    "id": "m1",
                    "desc": "academy test",
                    "status": "assigned",
                    "assigned_to": "agent-1",
                }]
            }),
            encoding="utf-8",
        )
        return root

    def test_unverified_result_is_blocked(self):
        root = self._root()
        result = persist_verified_execution(
            "m1",
            {
                "mission_id": "m1",
                "action_type": "academy.complete_stage",
                "idempotency_key": "mission:m1:execution",
                "evidence": {"changed": False},
                "execution_status": "success",
                "verified": False,
            },
            root=root,
        )
        self.assertEqual(result["status"], "blocked")

    def test_verified_result_moves_mission_to_executed(self):
        root = self._root()
        result = persist_verified_execution(
            "m1",
            {
                "mission_id": "m1",
                "action_type": "academy.complete_stage",
                "idempotency_key": "mission:m1:execution",
                "evidence": {"changed": True},
                "execution_status": "success",
                "verified": True,
                "started_at": "2026-09-13T00:00:00+00:00",
                "completed_at": "2026-09-13T00:00:01+00:00",
            },
            root=root,
        )
        self.assertEqual(result["status"], "executed")
        board = json.loads((root / "state" / "missions" / "board.json").read_text(encoding="utf-8"))
        self.assertEqual(board["missions"][0]["status"], "executed")
        result_path = Path(result["result_path"])
        self.assertTrue(result_path.exists())
        stored = json.loads(result_path.read_text(encoding="utf-8"))
        self.assertEqual(stored["mission_id"], "m1")
        self.assertTrue(stored["verified"])
        self.assertEqual(stored["mission_completion"], "pending")


if __name__ == "__main__":
    unittest.main()
