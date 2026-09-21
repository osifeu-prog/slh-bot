import unittest
from unittest.mock import patch

from core import stars_payment_authority


class StarsRevenueReconciliationTests(unittest.TestCase):
    def test_duplicate_charge_reconciles_revenue(self):
        with patch.object(
            stars_payment_authority.economy_service,
            "record_stars_payment",
            return_value={
                "status": "duplicate",
                "uid": "test-user",
                "credits": 100,
                "charge_id": "replay-charge",
            },
        ):
            with patch.object(
                stars_payment_authority.revenue_ledger,
                "record",
            ) as record:
                result = stars_payment_authority.record_stars_payment(
                    uid="test-user",
                    credits=100,
                    stars_paid=100,
                    currency="XTR",
                    telegram_payment_charge_id="replay-charge",
                )

        self.assertEqual(result["status"], "duplicate")
        record.assert_called_once_with(
            source="telegram_stars",
            amount=100,
            currency="XTR",
            reference="replay-charge",
            uid="test-user",
            meta={"kind": "telegram_stars_gross"},
        )


if __name__ == "__main__":
    unittest.main()
