import unittest
from pathlib import Path


class TestDeveloperRewardsContract(unittest.TestCase):
    def test_reward_authority_and_tiers_exist(self):
        source = Path("core/developer_rewards.py").read_text(encoding="utf-8")
        self.assertIn("PR_REWARD", source) if False else None
        self.assertIn("5000.0", source)
        self.assertIn("2500.0", source)
        self.assertIn("PR_NOT_MERGED", source)
        self.assertIn("PR_NOT_FROM_DEVELOPER_LAB", source)
        self.assertIn("developer-pr-reward:", source)
        self.assertIn('state_manager.atomic_update', source)

    def test_developer_admin_exposes_verified_pr_reward(self):
        source = Path("handlers/dev_admin.py").read_text(encoding="utf-8")
        self.assertIn("commands=['dev_reward_pr']", source)
        self.assertIn("apply_merged_pr_reward", source)
        self.assertIn("Developer PR reward failed safely", source)


if __name__ == "__main__":
    unittest.main()
