import unittest
from unittest.mock import patch

import core.arcade_engine as arcade_engine


class ArcadeEngineTests(unittest.TestCase):
    def setUp(self):
        arcade_engine.ACTIVE.clear()

    def test_insufficient_balance_does_not_start(self):
        with patch("core.arcade_engine.spend_credits", return_value=False) as spend:
            result = arcade_engine.start_game("1", now=100)

        self.assertEqual(result["status"], "insufficient_credits")
        spend.assert_called_once()

    def test_duplicate_start_does_not_charge_twice(self):
        with patch("core.arcade_engine.spend_credits", return_value=5) as spend, patch(
            "core.arcade_engine.new_question", return_value=("1 + 1 = ?", 2)
        ):
            first = arcade_engine.start_game("1", now=100)
            second = arcade_engine.start_game("1", now=101)

        self.assertEqual(first["status"], "started")
        self.assertEqual(second["status"], "already_active")
        spend.assert_called_once()

    def test_finish_is_idempotent_and_rewards_once(self):
        with patch("core.arcade_engine.spend_credits", return_value=5), patch(
            "core.arcade_engine.new_question", return_value=("1 + 1 = ?", 2)
        ), patch("core.arcade_engine.add_points") as reward:
            arcade_engine.start_game("1", now=100)
            arcade_engine.answer_game("1", "2", now=101)
            first = arcade_engine.finish_game("1")
            second = arcade_engine.finish_game("1")

        self.assertEqual(first["status"], "finished")
        self.assertEqual(second["status"], "already_finished")
        reward.assert_called_once()


if __name__ == "__main__":
    unittest.main()
