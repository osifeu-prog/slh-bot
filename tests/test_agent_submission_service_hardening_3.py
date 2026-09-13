import unittest

from core.agent_submission_service import APPROVAL_REWARD


class AgentSubmissionPolicyTests(unittest.TestCase):
    def test_approval_reward_is_fixed(self):
        self.assertEqual(APPROVAL_REWARD, 40)
