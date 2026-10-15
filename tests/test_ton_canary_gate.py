import os
import unittest
from unittest.mock import patch

from core import ton_deposit_service as service


CANARY_UID = "12345"
TREASURY = "0:" + "33" * 32


class TonCanaryGateTests(unittest.TestCase):
    def test_configured_canary_is_blocked_by_default_when_public_gate_is_closed(self):
        with patch.object(service, "_settings", return_value=(TREASURY, 100)):
            with patch.dict(
                os.environ,
                {
                    "TON_DEPOSITS_OPEN": "0",
                    "TON_DEPOSITS_CANARY_UID": CANARY_UID,
                    "TON_DEPOSITS_CANARY_SETTLEMENT_OPEN": "0",
                },
                clear=False,
            ):
                self.assertFalse(service.ton_settlement_allowed(CANARY_UID))
                self.assertFalse(service.ton_settlement_allowed("99999"))

    def test_canary_needs_both_uid_match_and_explicit_settlement_enable(self):
        with patch.object(service, "_settings", return_value=(TREASURY, 100)):
            with patch.dict(
                os.environ,
                {
                    "TON_DEPOSITS_OPEN": "0",
                    "TON_DEPOSITS_CANARY_UID": CANARY_UID,
                    "TON_DEPOSITS_CANARY_SETTLEMENT_OPEN": "1",
                },
                clear=False,
            ):
                self.assertTrue(service.ton_settlement_allowed(CANARY_UID))
                self.assertFalse(service.ton_settlement_allowed("99999"))

    def test_public_gate_does_not_depend_on_canary_enable_flag(self):
        with patch.object(service, "_settings", return_value=(TREASURY, 100)):
            with patch.object(service, "_verified_public_replay_evidence", return_value=True):
                with patch.dict(
                    os.environ,
                    {
                        "TON_DEPOSITS_OPEN": "1",
                        "TON_DEPOSITS_CANARY_UID": CANARY_UID,
                        "TON_DEPOSITS_CANARY_SETTLEMENT_OPEN": "0",
                    },
                    clear=False,
                ):
                    self.assertTrue(service.ton_settlement_allowed("99999"))

    def _valid_replay_db(self):
        tx_hash = "TON-TX-EMPIRICAL-001"
        return {
            "ton_replay_evidence": {
                CANARY_UID: {
                    "tx_hash": tx_hash,
                    "replay_count": 61,
                    "first_replay_at_epoch": 100.0,
                    "last_replay_at_epoch": 200.0,
                    "amount_ton": 0.01,
                }
            },
            "used_ton_txs": [tx_hash],
            "transactions": [{
                "uid": CANARY_UID,
                "type": "ton",
                "tx_hash": tx_hash,
                "ton_amount": 0.01,
                "credits": 1.0,
            }],
            "ledger": [{
                "uid": CANARY_UID,
                "reason": "ton:deposit",
                "before": 7.091775,
                "amount": 1.0,
                "after": 8.091775,
                "meta": {
                    "tx_hash": tx_hash,
                    "source": "ton_verified_binding_v1",
                    "binding_address_raw": "0:" + "22" * 32,
                    "ton_amount": 0.01,
                    "rate": "100",
                    "treasury": TREASURY,
                    "memo": f"SLH{CANARY_UID}",
                },
            }],
        }

    def test_public_readiness_fails_closed_without_matching_replay_evidence(self):
        with patch.object(service, "_settings", return_value=(TREASURY, 100)):
            with patch.object(service.state_manager, "load_db", return_value={}):
                with patch.dict(
                    os.environ,
                    {"TON_DEPOSITS_OPEN": "1", "TON_DEPOSITS_CANARY_UID": CANARY_UID},
                    clear=False,
                ):
                    result = service.ton_readiness()
        self.assertTrue(result["config_ready"])
        self.assertFalse(result["ready"])
        self.assertFalse(result["effective_open"])
        self.assertIn("TON_EMPIRICAL_REPLAY_EVIDENCE_MISSING", result["reasons"])

    def test_empirical_readiness_requires_one_matching_credit_and_ledger_row(self):
        db = self._valid_replay_db()
        with patch.dict(os.environ, {"TON_DEPOSITS_CANARY_UID": CANARY_UID}, clear=False):
            with patch.object(service.state_manager, "load_db", return_value=db):
                self.assertTrue(
                    service._verified_public_replay_evidence(
                        TREASURY, service.Decimal("100")
                    )
                )

        db["ledger"].append(dict(db["ledger"][0]))
        with patch.dict(os.environ, {"TON_DEPOSITS_CANARY_UID": CANARY_UID}, clear=False):
            with patch.object(service.state_manager, "load_db", return_value=db):
                self.assertFalse(
                    service._verified_public_replay_evidence(
                        TREASURY, service.Decimal("100")
                    )
                )

    def test_empirical_readiness_rejects_bad_balance_arithmetic(self):
        db = self._valid_replay_db()
        db["ledger"][0]["after"] = 9.0
        with patch.dict(os.environ, {"TON_DEPOSITS_CANARY_UID": CANARY_UID}, clear=False):
            with patch.object(service.state_manager, "load_db", return_value=db):
                self.assertFalse(
                    service._verified_public_replay_evidence(
                        TREASURY, service.Decimal("100")
                    )
                )


if __name__ == "__main__":
    unittest.main()
