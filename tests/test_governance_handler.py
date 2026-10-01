import unittest

from handlers.governance_handler import _parse_proposal_id


class GovernanceHandlerTests(unittest.TestCase):
    def test_parse_plain_proposal_id(self):
        self.assertEqual(_parse_proposal_id("7"), 7)

    def test_parse_hash_proposal_id(self):
        self.assertEqual(_parse_proposal_id("#7"), 7)
        self.assertEqual(_parse_proposal_id("  #64748 "), 64748)

    def test_parse_invalid_proposal_id(self):
        for value in ("", "#", "abc", "#abc", "0", "#0"):
            with self.assertRaisesRegex(ValueError, "PROPOSAL_ID_INVALID"):
                _parse_proposal_id(value)


if __name__ == "__main__":
    unittest.main()
