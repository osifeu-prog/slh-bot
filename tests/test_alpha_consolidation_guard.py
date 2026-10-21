"""Regression tests for the historical Alpha consolidation fail-closed guard."""
import unittest

from core.account_ledger_audit import audit_account_ledger


class AlphaConsolidationSourceClearanceGuardTests(unittest.TestCase):
    def test_unrelated_zero_before_row_cannot_clear_nonzero_source_wallet(self):
        target_uid = "8789977826"
        source_uid = "8791275334"
        db = {
            "users": {
                target_uid: {"wallet": {"credits": 11715.0, "staked": 794.0}},
                # Source later received 20 and spent 15; current balance is not zero.
                source_uid: {"wallet": {"credits": 5.0, "staked": 0.0}},
            },
            "ledger": [
                {
                    "time": "2026-08-20T14:18:40.628968+00:00",
                    "uid": target_uid, "before": 1314.0, "amount": 1.0,
                    "after": 1315.0, "reason": "P0_AUTHORITY_VERIFY",
                },
                {
                    "time": "2026-08-20T14:18:59.208393+00:00",
                    "uid": target_uid, "before": 1315.0, "amount": 1.0,
                    "after": 1316.0, "reason": "P0_AUTHORITY_VERIFY",
                },
                {
                    "time": "2026-08-22T16:12:41.978584+00:00",
                    "type": "alpha_consolidate", "from": source_uid,
                    "to": target_uid, "credits": 10449, "staked_moved": 50,
                    "reason": "OWNER_ONLY_CREDITS_POLICY",
                },
                {
                    "time": "2026-08-25T14:20:44.705458+00:00",
                    "uid": target_uid, "before": 11815.0, "amount": -100.0,
                    "after": 11715.0, "reason": "staking:stake",
                    "meta": {"staked_before": 136, "staked_after": 236},
                },
                # An unrelated later row with before=0 must not prove that the
                # source account was cleared by the August consolidation.
                {
                    "time": "2026-09-01T10:00:00+00:00",
                    "uid": source_uid, "before": 0.0, "amount": 20.0,
                    "after": 20.0, "reason": "admin:test_grant",
                },
            ],
        }

        result = audit_account_ledger(db, target_uid)

        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["continuity_break_count"], 1)
        finding = result["findings"][0]
        self.assertEqual(finding["type"], "SEQUENCE_GAP_REQUIRES_SOURCE_EVIDENCE")
        self.assertFalse(finding["reconciled"])
        evidence = finding["source_evidence"]
        self.assertFalse(evidence["resolves_gap"])
        consolidation = evidence["alpha_consolidations"][0]
        self.assertFalse(consolidation["verification_checks"]["source_account_cleared"])
        self.assertIn("source_account_cleared", consolidation["verification_failures"])


if __name__ == "__main__":
    unittest.main()
