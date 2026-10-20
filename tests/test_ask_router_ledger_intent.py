import unittest
from unittest.mock import patch

from core.ask_router import detect_intent, route


class LedgerIntentRoutingTests(unittest.TestCase):
    def test_numeric_alpha_gap_routes_to_ledger(self):
        self.assertEqual(
            detect_intent("תסביר לי את הפער של 10499 בין 1316 ל-11815"),
            "ledger",
        )

    def test_other_ledger_gaps_route_to_ledger(self):
        self.assertEqual(detect_intent("מה עם 2 הפערים האחרים?"), "ledger")
        self.assertEqual(detect_intent("what does alpha_consolidate mean?"), "ledger")

    def test_short_numeric_question_is_detected_as_ledger(self):
        self.assertEqual(detect_intent("תסביר את 10499"), "ledger")
        self.assertEqual(detect_intent("תסביר לי את הפער של 10499"), "ledger")

    def test_route_explains_failed_alpha_source_check_without_mutation(self):
        audit = {
            "status": "BLOCKED",
            "continuity_break_count": 1,
            "arithmetic_error_count": 0,
            "findings": [{
                "type": "SEQUENCE_GAP_REQUIRES_SOURCE_EVIDENCE",
                "previous": {"index": 1, "reason": "P0_AUTHORITY_VERIFY", "after": 1316.0},
                "next": {"index": 3, "reason": "staking:stake", "before": 11815.0},
                "delta_to_explain": 10499.0,
                "source_evidence": {
                    "source_match_status": "ALPHA_CONSOLIDATION_CONTEXT_REQUIRES_RECONCILIATION",
                    "resolves_gap": False,
                    "alpha_consolidations": [{
                        "index": 2,
                        "credits_component": 10449.0,
                        "staked_moved_component": 50.0,
                        "observed_balance_delta": 10499.0,
                        "verification_failures": ["source_account_cleared"],
                        "resolves_gap": False,
                    }],
                },
            }],
        }
        db = {
            "ledger": [{
                "type": "alpha_consolidate",
                "credits": 10449.0,
                "staked_moved": 50.0,
            }],
        }
        with (
            patch("core.ask_router.guard", return_value=True),
            patch("core.authority.is_owner", return_value=True),
            patch("state_manager.load_db", return_value=db),
            patch("core.account_ledger_audit.audit_account_ledger", return_value=audit),
        ):
            answer = route("תסביר את 10499", uid="8789977826")

        self.assertIn("מצב Ledger: BLOCKED", answer)
        self.assertIn("פער=10499", answer)
        self.assertIn("10449 Credits", answer)
        self.assertIn("50 Staked", answer)
        self.assertIn("חשבון המקור אינו מאומת כמאופס", answer)
        self.assertIn("הפער נשאר פתוח", answer)

    def test_route_keeps_ledger_details_owner_only(self):
        with (
            patch("core.ask_router.guard", return_value=True),
            patch("core.authority.is_owner", return_value=False),
            patch("state_manager.load_db", side_effect=AssertionError("DB must not be read for non-owner")),
        ):
            answer = route("תסביר את 10499", uid="5010371391")

        self.assertIn("זמין לבעלים בלבד", answer)
        self.assertNotIn("10449 Credits", answer)

    def test_staking_question_still_routes_to_staking(self):
        self.assertEqual(detect_intent("כמה סטייק יש לי?"), "staking")


if __name__ == "__main__":
    unittest.main()
