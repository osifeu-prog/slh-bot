import unittest

from core.alpha_control_plane import _token_integrity


class AlphaTokenIntegrityTests(unittest.TestCase):
    def test_zero_supply_does_not_require_historical_ledger(self):
        users = {
            "100": {"wallet": {"token_balance": 0}},
            "200": {"wallet": {"token_balance": 0.0}},
        }
        self.assertEqual(
            _token_integrity(users, None),
            (True, "zero SLH supply; ledger not yet required"),
        )

    def test_nonzero_supply_requires_ledger(self):
        users = {"100": {"wallet": {"token_balance": 1}}}
        ok, detail = _token_integrity(users, None)
        self.assertFalse(ok)
        self.assertEqual(detail, "non-zero SLH balances require a token ledger")

    def test_existing_ledger_is_accepted(self):
        users = {"100": {"wallet": {"token_balance": 0}}}
        self.assertEqual(
            _token_integrity(users, []),
            (True, "SLH token ledger available"),
        )


if __name__ == "__main__":
    unittest.main()
