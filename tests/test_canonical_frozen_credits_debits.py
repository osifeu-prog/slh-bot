import copy
import unittest
from unittest.mock import patch

from core import economy_service
from store import purchase_service


UID = "12345"
OTHER_UID = "67890"


class CanonicalFrozenCreditsDebitTests(unittest.TestCase):
    def setUp(self):
        self.db = {
            "users": {
                UID: {"wallet": {"credits": 100.0}, "frozen": False},
                OTHER_UID: {"wallet": {"credits": 50.0}, "frozen": False},
            },
            "ledger": [],
        }
        self.atomic_patch = patch.object(
            economy_service.state_manager,
            "atomic_update",
            side_effect=lambda mutate: mutate(self.db),
        )
        self.atomic_patch.start()
        self.addCleanup(self.atomic_patch.stop)

    def _debit(self, uid=UID, amount=-5.0, reason="arcade:entry", key="req-1", **extra):
        meta = {"source": "unit_test"}
        if key is not None:
            meta["idempotency_key"] = key
        meta.update(extra)
        return economy_service.record_transaction(
            uid=uid,
            amount=amount,
            reason=reason,
            meta=meta,
        )

    def test_frozen_arcade_debit_is_blocked_atomically(self):
        self.db["users"][UID]["frozen"] = True
        before = copy.deepcopy(self.db)

        with self.assertRaisesRegex(ValueError, "ACCOUNT_FROZEN"):
            self._debit(reason="arcade:entry")

        self.assertEqual(self.db, before)

    def test_frozen_generic_bridge_debit_is_blocked_atomically(self):
        self.db["users"][UID]["frozen"] = True
        before = copy.deepcopy(self.db)

        with self.assertRaisesRegex(ValueError, "ACCOUNT_FROZEN"):
            self._debit(reason="bridge:spend")

        self.assertEqual(self.db, before)

    def test_frozen_store_debit_is_blocked_by_the_same_canonical_boundary(self):
        self.db["users"][UID]["frozen"] = True
        before = copy.deepcopy(self.db)

        with self.assertRaisesRegex(ValueError, "ACCOUNT_FROZEN"):
            self._debit(reason="store:purchase")

        self.assertEqual(self.db, before)

    def test_normal_account_can_still_make_a_valid_debit(self):
        result = self._debit()
        self.assertEqual(result, 95.0)
        self.assertEqual(self.db["users"][UID]["wallet"]["credits"], 95.0)
        self.assertEqual(len(self.db["ledger"]), 1)

    def test_exact_debit_replay_after_freeze_is_read_only_noop(self):
        first = self._debit(reason="arcade:entry", key="stable-entry-7")
        self.assertEqual(first, 95.0)
        self.db["users"][UID]["frozen"] = True
        before_retry = copy.deepcopy(self.db)

        replay = self._debit(reason="arcade:entry", key="stable-entry-7")

        self.assertEqual(replay, 95.0)
        self.assertEqual(self.db, before_retry)

    def test_reused_key_with_different_amount_fails_before_freeze_gate(self):
        self._debit(reason="arcade:entry", key="stable-entry-8")
        self.db["users"][UID]["frozen"] = True
        before = copy.deepcopy(self.db)

        with self.assertRaisesRegex(ValueError, "IDEMPOTENCY_KEY_CONFLICT"):
            self._debit(amount=-6.0, reason="arcade:entry", key="stable-entry-8")

        self.assertEqual(self.db, before)

    def test_reused_key_with_different_uid_fails_without_mutation(self):
        self._debit(reason="arcade:entry", key="stable-entry-9")
        before = copy.deepcopy(self.db)

        with self.assertRaisesRegex(ValueError, "IDEMPOTENCY_KEY_CONFLICT"):
            self._debit(uid=OTHER_UID, amount=-5.0, reason="arcade:entry", key="stable-entry-9")

        self.assertEqual(self.db, before)

    def test_reused_key_with_different_reason_fails_without_mutation(self):
        self._debit(reason="arcade:entry", key="stable-entry-10")
        before = copy.deepcopy(self.db)

        with self.assertRaisesRegex(ValueError, "IDEMPOTENCY_KEY_CONFLICT"):
            self._debit(reason="store:purchase", key="stable-entry-10")

        self.assertEqual(self.db, before)

    def test_duplicate_ledger_entries_for_the_same_key_fail_closed(self):
        self._debit(reason="arcade:entry", key="duplicate-key-21")
        self.db["ledger"].append(copy.deepcopy(self.db["ledger"][0]))
        before = copy.deepcopy(self.db)

        with self.assertRaisesRegex(ValueError, "IDEMPOTENCY_KEY_CONFLICT"):
            self._debit(reason="arcade:entry", key="duplicate-key-21")

        self.assertEqual(self.db, before)

    def test_replay_with_missing_historical_after_balance_fails_closed(self):
        self._debit(reason="arcade:entry", key="missing-after-key-22")
        self.db["ledger"][0].pop("after")
        before = copy.deepcopy(self.db)

        with self.assertRaisesRegex(ValueError, "IDEMPOTENCY_KEY_CONFLICT"):
            self._debit(reason="arcade:entry", key="missing-after-key-22")

        self.assertEqual(self.db, before)

    def test_details_contract_reports_ambiguous_history_as_conflict(self):
        self._debit(reason="arcade:entry", key="details-duplicate-key-23")
        self.db["ledger"].append(copy.deepcopy(self.db["ledger"][0]))
        self.db["users"][UID]["frozen"] = True
        before = copy.deepcopy(self.db)

        result = economy_service.record_transaction(
            uid=UID,
            amount=-5.0,
            reason="arcade:entry",
            meta={"idempotency_key": "details-duplicate-key-23", "source": "unit_test"},
            return_details=True,
        )

        self.assertEqual(result["status"], "CONFLICT")
        self.assertEqual(result["credits_applied"], 0.0)
        self.assertEqual(self.db, before)

    def test_identity_metadata_conflict_fails_without_mutation(self):
        self._debit(
            reason="store:purchase",
            key="store-request-11",
            purchase_id="purchase:req-11",
            item_id="item-old",
        )
        before = copy.deepcopy(self.db)

        with self.assertRaisesRegex(ValueError, "IDEMPOTENCY_KEY_CONFLICT"):
            self._debit(
                reason="store:purchase",
                key="store-request-11",
                purchase_id="purchase:req-11",
                item_id="item-new",
            )

        self.assertEqual(self.db, before)

    def test_details_contract_reports_conflict_without_mutation(self):
        self._debit(reason="arcade:entry", key="details-key-12")
        self.db["users"][UID]["frozen"] = True
        before = copy.deepcopy(self.db)

        result = economy_service.record_transaction(
            uid=UID,
            amount=-8.0,
            reason="arcade:entry",
            meta={"idempotency_key": "details-key-12", "source": "unit_test"},
            return_details=True,
        )

        self.assertEqual(result["status"], "CONFLICT")
        self.assertEqual(result["credits_applied"], 0.0)
        self.assertEqual(self.db, before)

    def test_store_purchase_is_not_fulfilled_after_conflicting_key_replay(self):
        self.db["ledger"].append({
            "uid": UID,
            "before": 100.0,
            "amount": -10.0,
            "after": 90.0,
            "reason": "store:purchase",
            "meta": {
                "idempotency_key": "purchase:req-24:debit",
                "purchase_id": "purchase:req-24",
                "item_id": "old-item",
            },
        })
        self.db["users"][UID]["wallet"]["credits"] = 90.0
        items = {
            "new-item": {
                "type": "digital",
                "name": "New item",
                "price": 10.0,
                "grant": {"digital": "new-item"},
            }
        }

        with (
            patch.object(purchase_service.state_manager, "load_db", return_value=self.db),
            patch.object(purchase_service.state_manager, "atomic_update", side_effect=lambda mutate: mutate(self.db)),
            patch.object(purchase_service, "get_balance", return_value=90.0),
            patch.object(purchase_service, "load_items", return_value=items),
            patch.object(purchase_service, "resolve_item_id", return_value="new-item"),
            patch.object(purchase_service, "apply_grant") as apply_grant,
        ):
            success, result = purchase_service.purchase(
                UID, "new-item", request_id="req-24"
            )

        self.assertFalse(success)
        self.assertEqual(result, "PAYMENT_FAILED")
        self.assertEqual(self.db["users"][UID]["wallet"]["credits"], 90.0)
        self.assertEqual(len(self.db["ledger"]), 1)
        self.assertEqual(self.db["purchases"]["purchase:req-24"]["status"], "REJECTED")
        apply_grant.assert_not_called()

    def test_frozen_account_can_receive_positive_credit(self):
        self.db["users"][UID]["frozen"] = True
        result = economy_service.record_transaction(
            uid=UID,
            amount=2.0,
            reason="refund:adjustment",
            meta={"idempotency_key": "refund-key-13"},
        )
        self.assertEqual(result, 102.0)
        self.assertEqual(self.db["users"][UID]["wallet"]["credits"], 102.0)


if __name__ == "__main__":
    unittest.main()
