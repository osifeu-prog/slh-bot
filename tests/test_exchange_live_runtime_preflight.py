import copy
import unittest
from unittest.mock import patch

import handlers.exchange_handler as exchange_handler
import state_manager


def _runtime_open():
    return {
        "verified": True,
        "gate": "OPEN",
        "readiness": True,
        "verdict": "OPEN",
        "updated_at": 1791830000.0,
        "detail": "canonical public runtime proof passed",
    }


class FreshLiveExchangePreflightTests(unittest.TestCase):
    def test_closed_railway_gate_blocks_before_public_probe(self):
        with patch(
            "core.railway_control.control_plane_exchange_gate_status",
            return_value={"configured": "0"},
        ), patch.object(exchange_handler, "_fetch_public_exchange_status") as fetch:
            with self.assertRaises(exchange_handler.ExchangeFreshCheckBlocked) as caught:
                exchange_handler.require_fresh_live_exchange_proof()

        fetch.assert_not_called()
        self.assertEqual(caught.exception.check["railway_configured"], "0")
        self.assertIn("Railway", caught.exception.check["detail"])

    def test_unverified_live_beacon_blocks_even_when_railway_variable_is_open(self):
        with patch(
            "core.railway_control.control_plane_exchange_gate_status",
            return_value={"configured": "1"},
        ), patch.object(
            exchange_handler,
            "_fetch_public_exchange_status",
            return_value={
                "verified": False,
                "gate": "CLOSED",
                "readiness": False,
                "verdict": "BLOCKED",
                "updated_at": 1791830000.0,
                "detail": "canonical public runtime did not confirm ONLINE + OPEN + READY",
            },
        ):
            with self.assertRaises(exchange_handler.ExchangeFreshCheckBlocked) as caught:
                exchange_handler.require_fresh_live_exchange_proof()

        self.assertEqual(caught.exception.check["public_gate"], "CLOSED")
        self.assertFalse(caught.exception.check["execution_ready"])

    def test_open_live_proof_records_both_control_plane_and_public_beacon(self):
        with patch(
            "core.railway_control.control_plane_exchange_gate_status",
            return_value={"configured": "1"},
        ), patch.object(
            exchange_handler,
            "_fetch_public_exchange_status",
            return_value=_runtime_open(),
        ):
            proof = exchange_handler.require_fresh_live_exchange_proof()

        self.assertEqual(proof["status"], "PASS")
        self.assertEqual(proof["railway_configured"], "1")
        self.assertEqual(proof["public_gate"], "OPEN")
        self.assertEqual(proof["public_verdict"], "OPEN")
        self.assertTrue(proof["public_readiness"])
        self.assertIsNotNone(proof["checked_at"])

    def test_execution_blocked_by_live_gate_leaves_database_unchanged(self):
        db = {
            "users": {
                "buyer": {
                    "wallet": {
                        "credits": 50.0,
                        "token_balance": 0.0,
                        "live_token_balance": 0.0,
                        "exchange_reserved_slh": 0.0,
                        "exchange_reserved_credits": 0.0,
                    }
                }
            },
            "exchange_orders": {},
            "exchange_trades": [],
            "exchange_requests": {},
            "exchange_sequence": 0,
            "ledger": [],
            "slh_token_ledger": [],
        }
        before = copy.deepcopy(db)
        with patch.object(state_manager, "load_db", return_value=db), patch.object(
            state_manager, "atomic_update", side_effect=lambda mutate: mutate(db)
        ), patch(
            "core.railway_control.control_plane_exchange_gate_status",
            return_value={"configured": "0"},
        ), patch.object(exchange_handler, "_fetch_public_exchange_status") as fetch:
            with self.assertRaises(exchange_handler.ExchangeFreshCheckBlocked):
                exchange_handler.execute_exchange_order(
                    uid="buyer",
                    side="buy",
                    amount=1,
                    price=1,
                    request_id="req-closed-gate",
                )

        fetch.assert_not_called()
        self.assertEqual(db, before)

    def test_replay_returns_existing_receipt_without_requiring_current_open_gate(self):
        existing = {
            "order_id": "O0000000007",
            "filled": "1.00000000",
            "remaining": "0.00000000",
            "status": "filled",
            "trade_ids": ["T0000000008"],
            "execution_check": {
                "status": "PASS",
                "live_runtime_check": "PASS",
            },
        }
        db = {
            "exchange_requests": {"req-replay": existing},
        }
        with patch.object(state_manager, "load_db", return_value=db), patch(
            "core.railway_control.control_plane_exchange_gate_status",
            return_value={"configured": "0"},
        ) as status:
            result = exchange_handler.execute_exchange_order(
                uid="buyer",
                side="buy",
                amount=1,
                price=1,
                request_id="req-replay",
            )

        status.assert_not_called()
        self.assertEqual(result, existing)


if __name__ == "__main__":
    unittest.main()
