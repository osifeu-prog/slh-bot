import unittest
from unittest.mock import patch

from core import control_center


class ControlCenterFinancialTruthTests(unittest.TestCase):
    def test_financial_truth_is_read_only_and_reconciled(self):
        financial_truth = {
            "status": "LIVE_RECONCILED",
            "read_only": True,
            "owner": {
                "real_external_gross": 1122,
                "matched_count": 6,
                "mismatch_count": 0,
            },
        }
        with patch(
            "core.stars_financial_truth.build_stars_financial_truth",
            return_value=financial_truth,
        ):
            with patch(
                "core.system_check.run_system_checks",
                return_value={"status": "PASS"},
            ):
                with patch(
                    "core.alpha_control_plane.evaluate",
                    return_value={"status": "READY"},
                ), patch(
                    "core.alpha_control_plane.alpha_state",
                    return_value={"status": "OPEN"},
                ), patch(
                    "core.bnb_gate.bnb_readiness",
                    return_value={"effective_open": False},
                ), patch(
                    "core.bnb_gate.bnb_opening_evidence",
                    return_value={"status": "BLOCKED", "ready_to_open": False},
                ), patch(
                    "core.ton_deposit_service.deposits_are_open",
                    return_value=False,
                ):
                    result = control_center.get_release_state()

        self.assertEqual(result["financial_truth"]["status"], "LIVE_RECONCILED")
        self.assertTrue(result["financial_truth"]["read_only"])
        self.assertEqual(result["financial_truth"]["owner"]["real_external_gross"], 1122)
        self.assertEqual(result["financial_truth"]["owner"]["matched_count"], 6)
        self.assertEqual(result["financial_truth"]["owner"]["mismatch_count"], 0)
        self.assertEqual(result["evidence"]["financial_truth"], "LIVE_RECONCILED")


if __name__ == "__main__":
    unittest.main()
