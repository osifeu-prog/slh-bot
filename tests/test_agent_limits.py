import unittest
from unittest.mock import patch

from core.identity import OWNER_TELEGRAM_ID


class AgentLimitTests(unittest.TestCase):
    def test_regular_user_limit_is_two(self):
        from core.agent_policy import max_agents_for_user

        with patch("core.agent_policy.get_user", return_value={}):
            self.assertEqual(max_agents_for_user("1", now=2_000_000_000), 2)

    def test_launch_vip_user_limit_is_four(self):
        from core.agent_policy import max_agents_for_user

        user = {"vip_access_until": 2_000_000_100, "vip_launch_offer_qualified": True}
        with patch("core.agent_policy.get_user", return_value=user):
            self.assertEqual(
                max_agents_for_user("1", now=2_000_000_000),
                4,
            )

    def test_expired_launch_vip_returns_regular_limit(self):
        from core.agent_policy import max_agents_for_user

        user = {"vip_access_until": 1_999_999_999, "vip_launch_offer_qualified": True}
        with patch("core.agent_policy.get_user", return_value=user):
            self.assertEqual(
                max_agents_for_user("1", now=2_000_000_000),
                2,
            )

    def test_agent_creation_blocks_the_third_regular_agent(self):
        from core.agent_registry import create_agent

        existing = {
            "1": {"id": "1", "name": "a", "owner_id": "1"},
            "2": {"id": "2", "name": "b", "owner_id": "1"},
        }
        with patch("core.agent_registry.STORE.get_all", return_value=existing), patch(
            "core.agent_registry.can_create_agent", return_value=False
        ):
            with self.assertRaises(ValueError):
                create_agent("c", owner_id="1")


if __name__ == "__main__":
    unittest.main()
