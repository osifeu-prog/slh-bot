import unittest
from unittest.mock import patch

from core import vip_credits_service


class VIPCreditsServiceTests(unittest.TestCase):
    def test_manual_purchase_debits_150_and_grants_one_month_once(self):
        db = {
            "users": {
                "100": {
                    "wallet": {"credits": 200},
                    "permissions": [],
                    "vip_access_until": 0,
                }
            },
            "ledger": [],
        }
        with patch(
            "core.vip_credits_service.state_manager.atomic_update",
            side_effect=lambda mutate: mutate(db),
        ):
            first = vip_credits_service.purchase_vip_month_with_credits("100", now=1_800_000_000)
            second = vip_credits_service.purchase_vip_month_with_credits("100", now=1_800_000_001)

        self.assertEqual(first["status"], "APPLIED")
        self.assertEqual(first["credits_charged"], 150)
        self.assertEqual(first["credits_balance"], 50)
        self.assertEqual(second["status"], "ACTIVE")
        self.assertEqual(db["users"]["100"]["wallet"]["credits"], 50)
        self.assertEqual(len(db["ledger"]), 1)
        self.assertIn("vip_access", db["users"]["100"]["permissions"])

    def test_insufficient_credits_changes_nothing(self):
        db = {
            "users": {
                "100": {
                    "wallet": {"credits": 149.9},
                    "permissions": [],
                    "vip_access_until": 0,
                }
            },
            "ledger": [],
        }
        with patch(
            "core.vip_credits_service.state_manager.atomic_update",
            side_effect=lambda mutate: mutate(db),
        ):
            result = vip_credits_service.purchase_vip_month_with_credits("100", now=1_800_000_000)

        self.assertEqual(result["status"], "INSUFFICIENT_CREDITS")
        self.assertEqual(db["users"]["100"]["wallet"]["credits"], 149.9)
        self.assertEqual(db["ledger"], [])
        self.assertEqual(db["users"]["100"]["vip_access_until"], 0)

    def test_invalid_uid_is_rejected(self):
        with patch("core.vip_credits_service.state_manager.atomic_update") as update:
            result = vip_credits_service.purchase_vip_month_with_credits("../100", now=1_800_000_000)
        self.assertEqual(result["status"], "INVALID_USER_ID")
        update.assert_not_called()


if __name__ == "__main__":
    unittest.main()
