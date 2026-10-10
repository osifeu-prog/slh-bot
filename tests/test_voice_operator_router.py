import unittest
from unittest.mock import patch


from core.voice_operator_router import route_voice_operator_request


class VoiceOperatorRouterTests(unittest.TestCase):
    def test_unrecognized_transcript_is_left_for_conversational_ai(self):
        with patch("core.authority.get_role", return_value="OWNER"):
            self.assertIsNone(route_voice_operator_request("ספר לי על Bitcoin", "8789977826"))

    def test_owner_can_request_read_only_exchange_check_by_voice(self):
        result = {"ok": True, "detail": "order book and money invariants PASS", "public_open": True}
        with patch("core.authority.get_role", return_value="OWNER"), patch(
            "core.system_checks.check_exchange", return_value=result
        ) as check:
            answer = route_voice_operator_request("בדוק את הבורסה", "8789977826")

        check.assert_called_once_with()
        self.assertIn("Internal Exchange", answer)
        self.assertIn("order book and money invariants PASS", answer)
        self.assertIn("READ ONLY", answer)
        self.assertIn("לא בוצעו שינויים", answer)

    def test_non_privileged_test_account_cannot_read_operator_checks(self):
        with patch("core.authority.get_role", return_value="USER"), patch(
            "core.system_checks.check_exchange"
        ) as check:
            answer = route_voice_operator_request("בדוק את הבורסה", "224223270")

        check.assert_not_called()
        self.assertIn("OWNER/ADMIN/DEVELOPER", answer)

    def test_bnb_voice_check_shows_closed_when_proof_is_pending(self):
        result = {
            "ok": False,
            "detail": "BNB settlement remains CLOSED: empirical settlement proof pending/invalid",
            "public_open": False,
            "flag_open": False,
            "ready": True,
            "launch_ready": False,
            "empirical_status": "PENDING_EMPIRICAL",
        }
        with patch("core.authority.get_role", return_value="OWNER"), patch(
            "core.system_checks.check_bnb", return_value=result
        ) as check:
            answer = route_voice_operator_request("בדוק BNB", "8789977826")

        check.assert_called_once_with()
        self.assertIn("BNB", answer)
        self.assertIn("CLOSED", answer)
        self.assertIn("PENDING_EMPIRICAL", answer)
        self.assertIn("READ ONLY", answer)

    def test_voice_cannot_execute_financial_mutation_or_broadcast(self):
        with patch("core.authority.get_role", return_value="OWNER"), patch(
            "core.system_checks.check_bnb"
        ) as bnb_check:
            answer = route_voice_operator_request("פתח BNB ושלח ברודקאסט", "8789977826")

        bnb_check.assert_not_called()
        self.assertIn("לא בוצעה פעולה", answer)
        self.assertIn("בדוק BNB", answer)
        self.assertIn("בדוק את הבורסה", answer)
        self.assertNotIn("BNB נשאר CLOSED", answer)

    def test_full_system_check_uses_canonical_read_models_only(self):
        sample = {"ok": True, "detail": "PASS"}
        with patch("core.authority.get_role", return_value="OWNER"), patch(
            "core.system_checks.check_db", return_value=sample
        ) as db, patch(
            "core.system_checks.check_commands", return_value=sample
        ) as commands, patch(
            "core.system_checks.check_ux", return_value=sample
        ) as ux, patch(
            "core.system_checks.check_money", return_value=sample
        ) as money, patch(
            "core.system_checks.check_bnb", return_value=sample
        ) as bnb, patch(
            "core.system_checks.check_ton", return_value=sample
        ) as ton, patch(
            "core.system_checks.check_exchange", return_value=sample
        ) as exchange:
            answer = route_voice_operator_request("בדוק את כל המערכת", "8789977826")

        for mocked in (db, commands, ux, money, bnb, ton, exchange):
            mocked.assert_called_once()
        self.assertIn("READ ONLY", answer)
        self.assertIn("DB", answer)
        self.assertIn("BNB", answer)
        self.assertIn("Internal Exchange", answer)
        self.assertIn("לא בוצעו שינויים", answer)


if __name__ == "__main__":
    unittest.main()
