import unittest
from unittest.mock import patch

from core.identity import OWNER_TELEGRAM_ID


class VIPFulfillmentTests(unittest.TestCase):
    def test_launch_bundle_grants_all_benefits_once(self):
        from core.vip_fulfillment import apply_vip_benefits

        calls = []
        with patch(
            "core.vip_fulfillment.apply_grant",
            side_effect=lambda uid, grant, purchase_id=None: calls.append(
                (uid, grant, purchase_id)
            ) or {"ok": True, "type": next(iter(grant))},
        ) as grant, patch(
            "core.vip_fulfillment.economy_service.record_transaction",
            return_value=300,
        ) as credit, patch(
            "core.vip_fulfillment._mark_bundle_status"
        ) as mark:
            result = apply_vip_benefits(
                uid=str(OWNER_TELEGRAM_ID),
                charge_id="charge-1",
                launch_offer_qualified=True,
            )

        self.assertEqual(result["status"], "completed")
        self.assertEqual(grant.call_count, 2)
        credit.assert_called_once()
        self.assertEqual(credit.call_args.kwargs["amount"], 300)
        self.assertEqual(credit.call_args.kwargs["meta"]["idempotency_key"], "vip:charge-1:credits")
        self.assertTrue(mark.called)
        self.assertEqual(
            {item[1].get("plugin") for item in calls if "plugin" in item[1]},
            {"agent_os"},
        )
        self.assertEqual(
            {item[1].get("digital") for item in calls if "digital" in item[1]},
            {"emoji_vip"},
        )

    def test_non_launch_vip_does_not_receive_launch_bundle(self):
        from core.vip_fulfillment import apply_vip_benefits

        with patch("core.vip_fulfillment.apply_grant") as grant, patch(
            "core.vip_fulfillment.economy_service.record_transaction"
        ) as credit:
            result = apply_vip_benefits(
                uid="1",
                charge_id="charge-2",
                launch_offer_qualified=False,
            )

        self.assertEqual(result["status"], "skipped")
        grant.assert_not_called()
        credit.assert_not_called()


class VIPOfferWindowTests(unittest.TestCase):
    def test_offer_is_open_on_october_31_jerusalem_time(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        from core.vip_fulfillment import is_launch_offer_open

        dt = datetime(2026, 10, 31, 23, 59, 59, tzinfo=ZoneInfo("Asia/Jerusalem"))
        self.assertTrue(is_launch_offer_open(dt))

    def test_offer_is_closed_on_november_1(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        from core.vip_fulfillment import is_launch_offer_open

        dt = datetime(2026, 11, 1, 0, 0, 0, tzinfo=ZoneInfo("Asia/Jerusalem"))
        self.assertFalse(is_launch_offer_open(dt))


if __name__ == "__main__":
    unittest.main()
