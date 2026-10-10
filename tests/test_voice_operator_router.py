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

    def test_owner_can_request_read_only_mcp_control_plane_proof_by_voice(self):
        result = {
            "ok": True,
            "detail": "Telegram → MCP → Control Plane PASS · runtime_state=running · agent_count=4",
        }
        with patch("core.authority.get_role", return_value="OWNER"), patch(
            "handlers.mcp_proof_handler.read_mcp_proof", return_value=result
        ) as proof:
            answer = route_voice_operator_request("בדוק חיבורי האוטומציה", "8789977826")

        proof.assert_called_once_with()
        self.assertIn("MCP Control Plane", answer)
        self.assertIn("Telegram", answer)
        self.assertIn("agent_count=4", answer)
        self.assertIn("READ ONLY", answer)

    def test_non_privileged_account_cannot_probe_mcp_control_plane(self):
        with patch("core.authority.get_role", return_value="USER"), patch(
            "handlers.mcp_proof_handler.read_mcp_proof"
        ) as proof:
            answer = route_voice_operator_request("בדוק חיבורי האוטומציה", "224223270")

        proof.assert_not_called()
        self.assertIn("OWNER/ADMIN/DEVELOPER", answer)

    def test_owner_can_request_full_read_only_go_live_report_by_voice(self):
        report = "🧭 SLH OS GO-LIVE REPORT — READ ONLY\n✅ Internal Exchange: GREEN"
        with patch("core.authority.get_role", return_value="OWNER"), patch(
            "handlers.system_checks_handler._go_live_report_output",
            return_value=report,
        ) as go_live:
            answer = route_voice_operator_request("בדוק דוח Go-Live", "8789977826")

        go_live.assert_called_once_with("8789977826")
        self.assertIn("GO-LIVE REPORT", answer)
        self.assertIn("READ ONLY", answer)
        self.assertIn("Internal Exchange", answer)
        self.assertIn("לא נשלחו עסקאות", answer)

    def test_non_privileged_account_cannot_request_go_live_report_by_voice(self):
        with patch("core.authority.get_role", return_value="USER"), patch(
            "handlers.system_checks_handler._go_live_report_output"
        ) as go_live:
            answer = route_voice_operator_request("בדוק דוח Go-Live", "224223270")

        go_live.assert_not_called()
        self.assertIn("OWNER/ADMIN/DEVELOPER", answer)


if __name__ == "__main__":
    unittest.main()
