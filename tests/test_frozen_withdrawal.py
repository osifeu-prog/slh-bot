import copy
import unittest
from unittest.mock import patch

from handlers import withdraw_request_handler as wh


def _db(frozen):
    user = {"wallet": {"credits": 5.0}}
    if frozen:
        user["frozen"] = True
    return {"users": {"u1": user}, "ledger": [], "withdrawal_requests": {}}


class FrozenWithdrawalTests(unittest.TestCase):
    def _call(self, db, amount=10**9):
        with (
            patch.object(wh, "withdrawals_open", return_value=True),
            patch.object(wh, "valid_ton_address", return_value=True),
        ):
            try:
                wh.create_withdrawal(db, "u1", amount, "EQ-test-address")
            except ValueError as exc:
                return str(exc)
        return None

    def test_frozen_account_cannot_create_withdrawal(self):
        db = _db(True)
        before = copy.deepcopy(db)

        self.assertEqual(self._call(db), "ACCOUNT_FROZEN")
        self.assertEqual(db, before)
        self.assertEqual(db["users"]["u1"]["wallet"]["credits"], 5.0)
        self.assertEqual(db["ledger"], [])
        self.assertEqual(db["withdrawal_requests"], {})

    def test_unfrozen_account_reaches_balance_validation(self):
        db = _db(False)
        before = copy.deepcopy(db)

        self.assertEqual(self._call(db), "INSUFFICIENT_CREDITS")
        self.assertEqual(db, before)


if __name__ == "__main__":
    unittest.main()
