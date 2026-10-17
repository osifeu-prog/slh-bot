import copy
from decimal import Decimal
import unittest
from unittest.mock import patch

from core import economy_service


UID = "12345"
OTHER_UID = "67890"
TX = "abc123"
BOUND = "0:" + "22" * 32
TREASURY = "0:" + "33" * 32


class TonDepositIdempotencyIdentityTests(unittest.TestCase):
    def setUp(self):
        self.db = {
            "users": {
                UID: {"wallet": {"credits": 10.0}},
                OTHER_UID: {"wallet": {"credits": 25.0}},
            },
        }
        self.atomic_patch = patch.object(
            economy_service.state_manager,
            "atomic_update",
            side_effect=lambda mutate: mutate(self.db),
        )
        self.atomic_patch.start()
        self.addCleanup(self.atomic_patch.stop)

    def _meta(self):
        return {
            "idempotency_key": f"TON-DEPOSIT-{TX.lower()}",
            "source": "ton_verified_binding_v1",
            "binding_address_raw": BOUND,
            "treasury": TREASURY,
            "memo": f"SLH{UID}",
            "rate": "100",
            "utime": 1_760_000_000,
            "lt": "987654",
            "deposit_intent_id": "intent-original",
        }

    def _record(self, uid=UID, credits=100.0, ton_amount=1.0, meta=None):
        return economy_service.record_ton_deposit(
            uid=uid,
            credits=credits,
            ton_amount=ton_amount,
            tx_hash=TX,
            meta=self._meta() if meta is None else meta,
        )

    def _settle_once(self):
        result = self._record()
        self.assertEqual(result, 110.0)
        self.assertEqual(self.db["users"][UID]["wallet"]["credits"], 110.0)
        self.assertEqual(self.db["used_ton_txs"], [TX])
        self.assertEqual(len(self.db["transactions"]), 1)
        self.assertEqual(len(self.db["ledger"]), 1)

    def test_exact_replay_is_a_noop_after_canonical_identity_validation(self):
        self._settle_once()
        before = copy.deepcopy(self.db)

        result = self._record()

        self.assertIsNone(result)
        self.assertEqual(self.db, before)

    def test_same_hash_with_different_uid_is_a_conflict(self):
        self._settle_once()
        before = copy.deepcopy(self.db)

        with self.assertRaisesRegex(ValueError, "TON_DEPOSIT_IDENTITY_CONFLICT"):
            self._record(uid=OTHER_UID)

        self.assertEqual(self.db, before)

    def test_same_hash_with_different_credits_amount_is_a_conflict(self):
        self._settle_once()
        before = copy.deepcopy(self.db)

        with self.assertRaisesRegex(ValueError, "TON_DEPOSIT_IDENTITY_CONFLICT"):
            self._record(credits=101.0)

        self.assertEqual(self.db, before)

    def test_same_hash_with_different_ton_amount_is_a_conflict(self):
        self._settle_once()
        before = copy.deepcopy(self.db)

        with self.assertRaisesRegex(ValueError, "TON_DEPOSIT_IDENTITY_CONFLICT"):
            self._record(ton_amount=2.0)

        self.assertEqual(self.db, before)

    def test_same_hash_with_different_deposit_intent_is_a_conflict(self):
        self._settle_once()
        before = copy.deepcopy(self.db)
        changed = self._meta()
        changed["deposit_intent_id"] = "intent-new"

        with self.assertRaisesRegex(ValueError, "TON_DEPOSIT_IDENTITY_CONFLICT"):
            self._record(meta=changed)

        self.assertEqual(self.db, before)

    def test_same_hash_with_changed_treasury_is_a_conflict(self):
        self._settle_once()
        before = copy.deepcopy(self.db)
        changed = self._meta()
        changed["treasury"] = "0:" + "44" * 32

        with self.assertRaisesRegex(ValueError, "TON_DEPOSIT_IDENTITY_CONFLICT"):
            self._record(meta=changed)

        self.assertEqual(self.db, before)

    def test_used_hash_without_unique_transaction_and_ledger_evidence_is_unknown(self):
        self.db["used_ton_txs"] = [TX]
        before = copy.deepcopy(self.db)

        with self.assertRaisesRegex(ValueError, "TON_DEPOSIT_IDENTITY_UNKNOWN"):
            self._record()

        self.assertEqual(self.db, before)

    def test_source_rows_without_used_hash_index_fail_closed(self):
        self._settle_once()
        self.db.pop("used_ton_txs")
        before = copy.deepcopy(self.db)

        with self.assertRaisesRegex(ValueError, "TON_DEPOSIT_IDENTITY_UNKNOWN"):
            self._record()

        self.assertEqual(self.db, before)

    def test_duplicate_source_rows_are_not_accepted_as_exact_replay(self):
        self._settle_once()
        self.db["transactions"].append(copy.deepcopy(self.db["transactions"][0]))
        before = copy.deepcopy(self.db)

        with self.assertRaisesRegex(ValueError, "TON_DEPOSIT_IDENTITY_UNKNOWN"):
            self._record()

        self.assertEqual(self.db, before)

    def test_duplicate_used_hash_markers_fail_closed(self):
        self._settle_once()
        self.db["used_ton_txs"].append(TX.upper())
        before = copy.deepcopy(self.db)

        with self.assertRaisesRegex(ValueError, "TON_DEPOSIT_IDENTITY_UNKNOWN"):
            self._record()

        self.assertEqual(self.db, before)


    def test_boolean_credits_are_rejected_before_mutation(self):
        before = copy.deepcopy(self.db)
        with self.assertRaisesRegex(TypeError, "credits must be numeric"):
            self._record(credits=True)
        self.assertEqual(self.db, before)

    def test_non_finite_credits_are_rejected_before_mutation(self):
        for amount in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(amount=amount):
                before = copy.deepcopy(self.db)
                with self.assertRaisesRegex(ValueError, "INVALID_TON_CREDITS"):
                    self._record(credits=amount)
                self.assertEqual(self.db, before)

    def test_boolean_ton_amount_is_rejected_before_mutation(self):
        before = copy.deepcopy(self.db)
        with self.assertRaisesRegex(TypeError, "ton_amount must be numeric"):
            self._record(ton_amount=True)
        self.assertEqual(self.db, before)

    def test_non_finite_ton_amount_is_rejected_before_mutation(self):
        for amount in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(amount=amount):
                before = copy.deepcopy(self.db)
                with self.assertRaisesRegex(ValueError, "INVALID_TON_AMOUNT"):
                    self._record(ton_amount=amount)
                self.assertEqual(self.db, before)

if __name__ == "__main__":
    unittest.main()


class TonDepositServiceCallerTests(unittest.TestCase):
    """Exercise the service boundary around the canonical identity guard."""

    def _transaction(self):
        return {
            "tx_hash": TX,
            "from": BOUND,
            "to": TREASURY,
            "amount_ton": 1.0,
            "memo": f"SLH{UID}",
            "utime": 1_760_000_000,
            "lt": "987654",
        }

    def _binding(self):
        return {"address": BOUND, "address_raw": BOUND}

    def test_identity_conflict_does_not_record_replay_or_match_new_intent(self):
        from core import ton_deposit_service

        with (
            patch.object(ton_deposit_service, "_match_deposit_intent", return_value="intent-new"),
            patch.object(
                ton_deposit_service,
                "record_ton_deposit",
                side_effect=ValueError("TON_DEPOSIT_IDENTITY_CONFLICT"),
            ) as record,
            patch.object(ton_deposit_service, "_record_ton_replay_evidence") as replay_evidence,
            patch.object(ton_deposit_service, "_mark_deposit_intent_matched") as mark_intent,
        ):
            with self.assertRaisesRegex(ValueError, "TON_DEPOSIT_IDENTITY_CONFLICT"):
                ton_deposit_service._settle_observed_transaction(
                    UID, self._transaction(), TREASURY, Decimal("100"), self._binding()
                )

        record.assert_called_once()
        replay_evidence.assert_not_called()
        mark_intent.assert_not_called()

    def test_exact_replay_after_original_intent_matched_does_not_match_new_intent(self):
        from decimal import Decimal
        from core import ton_deposit_service

        with (
            patch.object(ton_deposit_service, "_match_deposit_intent", return_value=None),
            patch.object(ton_deposit_service, "record_ton_deposit", return_value=None),
            patch.object(ton_deposit_service, "_record_ton_replay_evidence") as replay_evidence,
            patch.object(ton_deposit_service, "_mark_deposit_intent_matched") as mark_intent,
        ):
            result = ton_deposit_service._settle_observed_transaction(
                UID, self._transaction(), TREASURY, Decimal("100"), self._binding()
            )

        self.assertTrue(result["ok"])
        self.assertTrue(result["idempotent"])
        self.assertEqual(result["credits"], 0.0)
        replay_evidence.assert_called_once()
        mark_intent.assert_called_once_with(None, TX, True)

    def test_matched_intent_is_not_selected_as_a_new_pending_intent(self):
        from core import ton_deposit_service

        db = {
            "ton_deposit_intents": {
                "intent-original": {
                    "uid": UID,
                    "status": "matched",
                    "amount_nano": 1_000_000_000,
                    "memo": f"SLH{UID}",
                    "treasury": TREASURY,
                    "binding_address_raw": BOUND,
                    "created_at_epoch": 1_759_999_000,
                    "expires_at_epoch": 1_760_001_000,
                }
            }
        }
        with patch.object(ton_deposit_service.state_manager, "load_db", return_value=db):
            matched = ton_deposit_service._match_deposit_intent(
                UID, self._transaction(), "intent-original"
            )

        self.assertIsNone(matched)
