import unittest
from unittest.mock import patch

from core.investor_read_model import get_investor_snapshot


class InvestorReadModelTests(unittest.TestCase):
    @patch("core.investor_read_model._load_reward_ledger")
    @patch("core.investor_read_model._load_courses", return_value={"academy-101": {}})
    @patch("core.investor_read_model.state_manager.load_db")
    def test_snapshot_is_user_scoped_and_read_only(self, load_db, _courses, reward_ledger):
        load_db.return_value = {
            "users": {
                "100": {
                    "name": "Alice",
                    "role": "student",
                    "wallet": {"credits": 120, "staked": 30, "token_balance": 4},
                    "academy": {"courses": {"academy-101": {"stage": 2}}},
                    "gamification": {"points": 55},
                }
            },
            "tasks": {
                "mine": {"owner_id": "100", "title": "My task", "reward": 10, "done_by": []},
                "other": {"owner_id": "200", "title": "Other task", "reward": 99, "done_by": []},
                "shared": {"owner_id": "", "title": "System task", "reward": 1, "done_by": ["100"]},
            },
            "ledger": [
                {"uid": "100", "amount": 1000, "reason": "payment:telegram_stars", "time": "t0"},
                {"uid": "100", "amount": 10, "reason": "task_reward", "time": "t1"},
                {"uid": "200", "amount": 99, "reason": "task_reward", "time": "t2"},
            ],
        }
        reward_ledger.return_value = [
            {"user": "100", "reason": "task_reward", "credits": 10, "points": 5, "timestamp": "r1"},
            {"user": "100", "reason": "payment:telegram_stars", "credits": 1000, "points": 0, "timestamp": "r0"},
            {"user": "100", "reason": "older_reward", "credits": 1, "points": 0, "timestamp": "r-1"},
            {"user": "200", "reason": "task_reward", "credits": 99, "points": 9, "timestamp": "r2"},
        ]

        snapshot = get_investor_snapshot("100")

        self.assertEqual(snapshot["identity"]["uid"], "100")
        self.assertEqual(snapshot["wallet"]["credits"], 120)
        self.assertEqual(snapshot["rewards"]["points"], 55)
        self.assertEqual(snapshot["rewards"]["credits"], 1011)
        self.assertEqual(snapshot["rewards"]["recent"][0]["reason"], "task_reward")
        self.assertEqual(len(snapshot["rewards"]["recent"]), 3)
        self.assertEqual(snapshot["academy"]["enrolled"], ["academy-101"])
        self.assertEqual([t["id"] for t in snapshot["tasks"]["personal"]], ["mine"])
        self.assertEqual(snapshot["tasks"]["open"], 1)
        self.assertEqual(snapshot["tasks"]["completed"], 0)
        self.assertEqual(snapshot["airdrop"]["status"], "not_connected")
        load_db.assert_called_once()
        reward_ledger.assert_called_once()

    @patch("core.investor_read_model.state_manager.load_db", return_value={"users": {}})
    def test_unknown_user_rejected(self, _load_db):
        with self.assertRaisesRegex(ValueError, "USER_NOT_FOUND"):
            get_investor_snapshot("404")


if __name__ == "__main__":
    unittest.main()
