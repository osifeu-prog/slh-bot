import unittest
from unittest.mock import patch

from store import grant_engine


class StoreBundleGrantTests(unittest.TestCase):
    def setUp(self):
        self.user = {"wallet": {"credits": 0}, "permissions": [], "inventory": {}}
        self.db = {"users": {"100": self.user}, "ledger": []}

        self.atomic = patch(
            "store.grant_engine.state_manager.atomic_update",
            side_effect=lambda mutate: mutate(self.db),
        )
        self.atomic.start()
        self.addCleanup(self.atomic.stop)

        self.get_user = patch(
            "store.grant_engine.profile_manager.get_user",
            side_effect=lambda uid: self.user,
        )
        self.get_user.start()
        self.addCleanup(self.get_user.stop)

        def update_user(uid, changes):
            self.user.update(changes)
            return self.user

        self.update_user = patch(
            "store.grant_engine.profile_manager.update_user",
            side_effect=update_user,
        )
        self.update_user.start()
        self.addCleanup(self.update_user.stop)

        self.clock = patch("store.grant_engine.time.time", return_value=1_800_000_000)
        self.clock.start()
        self.addCleanup(self.clock.stop)

        def record_transaction(**kwargs):
            key = (kwargs.get("meta") or {}).get("idempotency_key")
            previous = next(
                (
                    row for row in self.db["ledger"]
                    if isinstance(row.get("meta"), dict)
                    and row["meta"].get("idempotency_key") == key
                ),
                None,
            )
            if previous is not None:
                if (
                    str(previous.get("uid")) != str(kwargs.get("uid"))
                    or float(previous.get("amount", 0)) != float(kwargs.get("amount", 0))
                    or str(previous.get("reason")) != str(kwargs.get("reason"))
                ):
                    return {"status": "CONFLICT"}
                return {"status": "DUPLICATE"}
            amount = float(kwargs["amount"])
            before = float(self.user["wallet"].get("credits", 0))
            after = before + amount
            self.user["wallet"]["credits"] = after
            self.db["ledger"].append({
                "uid": str(kwargs["uid"]),
                "before": before,
                "amount": amount,
                "after": after,
                "reason": kwargs["reason"],
                "meta": kwargs["meta"],
            })
            return {"status": "APPLIED", "balance_after": after}

        self.record_transaction = patch(
            "core.economy_service.record_transaction",
            side_effect=record_transaction,
        )
        self.record_transaction.start()
        self.addCleanup(self.record_transaction.stop)

    def test_bundle_applies_allowlisted_grants_and_bonuses_once(self):
        grant = {
            "bundle": [
                {"permission": "trade_pro"},
                {"digital": "emoji_slh"},
            ],
            "credits_bonus": 50,
            "vip_months_bonus": 1,
        }
        first = grant_engine.apply_grant("100", grant, purchase_id="stars:charge-1")
        expiry_first = self.user["vip_access_until"]
        second = grant_engine.apply_grant("100", grant, purchase_id="stars:charge-1")

        self.assertTrue(first["ok"])
        self.assertTrue(second["ok"])
        self.assertEqual(self.user["wallet"]["credits"], 50)
        self.assertEqual(expiry_first, self.user["vip_access_until"])
        self.assertEqual(self.user["permissions"].count("vip_access"), 1)
        self.assertEqual(len([r for r in self.db["ledger"] if r["reason"] == "store:bundle_bonus"]), 1)
        self.assertEqual(len([r for r in self.db["vip_bonus_awards"].values() if r.get("purchase_id") == "stars:charge-1"]), 1)

    def test_bundle_rejects_nested_or_unknown_grant_types(self):
        with self.assertRaisesRegex(ValueError, "BUNDLE_CHILD_GRANT_INVALID"):
            grant_engine.apply_grant(
                "100",
                {"bundle": [{"bundle": [{"permission": "owner"}]}]},
                purchase_id="bad-purchase",
            )

    def test_bundle_rejects_bonus_without_purchase_id(self):
        with self.assertRaisesRegex(ValueError, "BUNDLE_BONUS_PURCHASE_ID_REQUIRED"):
            grant_engine.apply_grant(
                "100",
                {"bundle": [{"permission": "trade_pro"}], "credits_bonus": 50},
            )


if __name__ == "__main__":
    unittest.main()
