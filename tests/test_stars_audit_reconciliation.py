import unittest
from unittest.mock import patch

from handlers.stars_audit_handler import _local_snapshot


class StarsAuditReconciliationTests(unittest.TestCase):
    def test_store_vip_and_credits_share_one_charge_map(self):
        real_credits = "stx-credits"
        vip = "stx-vip"
        store_a = "stx-store-a"
        store_b = "stx-store-b"
        store_c = "stx-store-c"

        db = {
            "transactions": [
                {
                    "telegram_payment_charge_id": real_credits,
                    "uid": "1001",
                    "stars_paid": 100,
                },
                {
                    "telegram_payment_charge_id": "test",
                    "uid": "8789977826",
                    "stars_paid": 100,
                },
                {
                    "telegram_payment_charge_id": "fakepay_8789977826",
                    "uid": "8789977826",
                    "stars_paid": 50,
                },
                {
                    "telegram_payment_charge_id": "test2",
                    "uid": "8789977826",
                    "stars_paid": 10,
                },
            ],
            "vip_subscriptions": {
                vip: {
                    "uid": "2002",
                    "stars": 499,
                    "status": "ACTIVE",
                }
            },
            "star_item_orders": {
                "stars:" + store_a: {
                    "charge_id": store_a,
                    "uid": "3001",
                    "stars_paid": 199,
                    "status": "FULFILLED",
                    "item_id": "agent_os",
                },
                "stars:" + store_b: {
                    "charge_id": store_b,
                    "uid": "3002",
                    "stars_paid": 199,
                    "status": "FULFILLED",
                    "item_id": "agent_os",
                },
                "stars:" + store_c: {
                    "charge_id": store_c,
                    "uid": "3003",
                    "stars_paid": 25,
                    "status": "FULFILLED",
                    "item_id": "emoji_bitcoin",
                },
            },
            "revenue_ledger": [
                {"currency": "XTR", "reference": real_credits},
                {"currency": "XTR", "reference": vip},
                {"currency": "XTR", "reference": store_a},
                {"currency": "XTR", "reference": store_b},
                {"currency": "XTR", "reference": store_c},
                {
                    "currency": "XTR",
                    "reference": "boundary-test-xtr",
                    "uid": "test-user",
                    "meta": {"kind": "telegram_stars_gross"},
                },
            ],
        }

        with patch(
            "handlers.stars_audit_handler.state_manager.load_db",
            return_value=db,
        ):
            _, confirmed, revenue_refs, local_test_ids, test_revenue_refs = (
                _local_snapshot()
            )

        self.assertEqual(len(confirmed), 8)
        self.assertEqual(
            sum(row["stars"] for row in confirmed.values()),
            1182,
        )
        self.assertEqual(
            {real_credits, vip, store_a, store_b, store_c},
            set(confirmed) - local_test_ids,
        )
        self.assertEqual({"test", "test2", "fakepay_8789977826"}, local_test_ids)
        self.assertIn("boundary-test-xtr", test_revenue_refs)
        self.assertEqual(
            revenue_refs,
            {
                real_credits,
                vip,
                store_a,
                store_b,
                store_c,
                "boundary-test-xtr",
            },
        )

    def test_vip_accepts_legacy_stars_field(self):
        charge = "stx-vip-legacy"
        db = {
            "transactions": [],
            "vip_subscriptions": {
                charge: {
                    "uid": "2002",
                    "stars": 499,
                    "status": "ACTIVE",
                }
            },
            "star_item_orders": {},
            "revenue_ledger": [],
        }

        with patch(
            "handlers.stars_audit_handler.state_manager.load_db",
            return_value=db,
        ):
            _, confirmed, _, _, _ = _local_snapshot()

        self.assertEqual(confirmed[charge]["stars"], 499)
        self.assertEqual(confirmed[charge]["kind"], "vip")


if __name__ == "__main__":
    unittest.main()
