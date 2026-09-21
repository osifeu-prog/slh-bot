import json
import tempfile
import unittest
from unittest.mock import patch


class EarningsReadModelTests(unittest.TestCase):
    def test_read_model_separates_cash_from_internal_rewards(self):
        state = {
            "users": {"1": {"role": "OWNER", "wallet": {"credits": 5, "staked": 100, "token_balance": 2, "revenue_share_claimable": 3}, "gamification": {"points": 90}}},
            "stake_positions": {"p1": {"uid": "1", "status": "locked", "amount": 100}},
            "reward_pools": {"p1": {"status": "pending", "reward": 1.25}},
            "revenue_distributions": {"2026-09": {"total_distributed": 10}},
            "revenue_share_pool": {"last_distribution": "2026-09", "total_distributed": 10},
            "revenue_ledger": [{"source": "telegram_stars", "amount": 100, "currency": "XTR", "reference": "r1"}],
        }
        import state_manager
        with patch.object(state_manager, "load_db", return_value=state):
            from core.earnings_read_model import get_earnings
            result = get_earnings("1")
        self.assertEqual(result["earnings"]["revenue_share_claimable_credits"], 3)
        self.assertEqual(result["earnings"]["staking_reward_pending_credits"], 1.25)
        self.assertEqual(result["cash"]["status"], "telegram_stars_withdrawal_external")
        self.assertEqual(result["system_revenue"]["confirmed_external_revenue_totals"]["XTR"], 100)
        self.assertTrue(result["read_only"])

    def test_read_model_does_not_mutate_state(self):
        state = {"users": {"2": {"wallet": {"credits": 8}}}, "revenue_ledger": []}
        snapshot = json.dumps(state, sort_keys=True)
        import state_manager
        with patch.object(state_manager, "load_db", return_value=state):
            from core.earnings_read_model import get_earnings
            get_earnings("2")
        self.assertEqual(json.dumps(state, sort_keys=True), snapshot)


if __name__ == "__main__":
    unittest.main()
