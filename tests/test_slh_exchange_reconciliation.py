import unittest
from unittest.mock import patch

import core.slh_exchange_reconciliation as reconciliation

from core.slh_exchange_reconciliation import audit_db


class ExchangeReconciliationTests(unittest.TestCase):
    def test_cancelled_sell_with_manual_correction_is_not_passed(self):
        db = {
            "exchange_order_archive": {
                "O0000000009": {
                    "id": "O0000000009", "uid": "6526198118", "uid_suffix": "8118", "side": "sell",
                    "status": "cancelled", "original_amount": "10000", "remaining_amount": "0"
                }
            },
            "ledger": [
                {"uid": "6526198118", "amount": -10000, "reason": "exchange:sell_reserve",
                 "event_id": "reserve:O0000000009", "meta": {"order_id": "O0000000009"}},
                {"uid": "6526198118", "amount": 10000, "reason": "exchange:missed_release_correction",
                 "meta": {"order_id": "O0000000009", "event_id": "correction:O0000000009"}},
            ],
            "slh_token_ledger": [],
        }
        report = audit_db(db)
        codes = {item["code"] for item in report["findings"]}
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["release_readiness_status"], "BLOCKED")
        self.assertGreater(report["release_blocking_finding_count"], 0)
        self.assertIn("CANCELLED_SELL_ORDER_MISSING_NORMAL_RELEASE", codes)
        self.assertIn("MANUAL_RESERVE_CORRECTION_REQUIRES_REVIEW", codes)
        missing_release = next(item for item in report["findings"] if item["code"] == "CANCELLED_SELL_ORDER_MISSING_NORMAL_RELEASE")
        self.assertEqual(missing_release["uid_suffix"], "8118")
        correction = next(item for item in report["findings"] if item["code"] == "MANUAL_RESERVE_CORRECTION_REQUIRES_REVIEW")
        self.assertEqual(correction["correction_delta"], "10000")

    def test_normal_release_balances_legacy_ledger_reserve(self):
        db = {
            "exchange_orders": {
                "O1": {"id": "O1", "uid": "42", "side": "sell", "status": "cancelled"}
            },
            "ledger": [
                {"uid": "42", "amount": -100, "reason": "exchange:sell_reserve",
                 "event_id": "reserve:O1", "meta": {"order_id": "O1"}},
                {"uid": "42", "amount": 100, "reason": "exchange:cancel_release",
                 "event_id": "release:O1", "meta": {"order_id": "O1"}},
            ],
            "slh_token_ledger": [],
        }
        report = audit_db(db)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["finding_count"], 0)

    def test_canonical_token_ledger_positive_amounts_balance_by_event_kind(self):
        db = {
            "exchange_orders": {
                "O2": {"id": "O2", "uid": "42", "side": "sell", "status": "cancelled"}
            },
            "ledger": [],
            "slh_token_ledger": [
                {
                    "event_id": "exchange:reserve_slh:O2",
                    "from_uid": "42",
                    "to_uid": "__EXCHANGE_RESERVE__",
                    "amount": 100.0,
                    "reason": "exchange:sell_reserve",
                    "kind": "exchange_reserve",
                    "order_id": "O2",
                },
                {
                    "event_id": "exchange:release_slh:O2",
                    "from_uid": "__EXCHANGE_RESERVE__",
                    "to_uid": "42",
                    "amount": 100.0,
                    "reason": "exchange:cancel_release_slh",
                    "kind": "exchange_release",
                    "order_id": "O2",
                },
            ],
        }
        report = audit_db(db)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["finding_count"], 0)

    def test_no_matched_reserves_is_unknown_not_pass(self):
        report = audit_db({"exchange_orders": {}, "ledger": [], "slh_token_ledger": []})
        self.assertEqual(report["status"], "UNKNOWN")
        self.assertEqual(report["release_readiness_status"], "BLOCKED")
        self.assertIn("RESERVE_HISTORY_NOT_PROVEN", {
            item["code"] for item in report["release_blocking_findings"]
        })
        self.assertIn("NO_CANCELLED_SELL_ORDERS_WITH_RESERVE_FOUND", {item["code"] for item in report["findings"]})

    def test_invalid_reserve_amount_fails_closed(self):
        db = {
            "exchange_orders": {
                "O2": {"id": "O2", "uid": "42", "side": "sell", "status": "cancelled"}
            },
            "ledger": [
                {"uid": "42", "amount": None, "reason": "exchange:sell_reserve",
                 "meta": {"order_id": "O2", "event_id": "reserve:O2"}},
                {"uid": "42", "amount": 100, "reason": "exchange:cancel_release",
                 "meta": {"order_id": "O2", "event_id": "release:O2"}},
            ],
            "slh_token_ledger": [],
        }
        report = audit_db(db)
        self.assertEqual(report["status"], "FAIL")
        self.assertIn("INVALID_RESERVE_LEDGER_AMOUNT", {item["code"] for item in report["findings"]})

    def test_audit_never_mutates_input(self):
        db = {"exchange_orders": {}, "ledger": [], "slh_token_ledger": []}
        before = repr(db)
        audit_db(db)
        self.assertEqual(repr(db), before)


    def test_mirrored_events_across_ledgers_are_not_silently_deduplicated(self):
        db = {
            "exchange_orders": {
                "O3": {"id": "O3", "uid": "42", "side": "sell", "status": "cancelled"}
            },
            "ledger": [
                {"uid": "42", "amount": -100, "reason": "exchange:sell_reserve",
                 "event_id": "shared-reserve-O3", "meta": {"order_id": "O3"}},
                {"uid": "42", "amount": 100, "reason": "exchange:cancel_release",
                 "event_id": "shared-release-O3", "meta": {"order_id": "O3"}},
            ],
            "slh_token_ledger": [
                {"amount": 100, "reason": "exchange:sell_reserve",
                 "kind": "exchange_reserve", "event_id": "shared-reserve-O3", "order_id": "O3"},
                {"amount": 100, "reason": "exchange:cancel_release_slh",
                 "kind": "exchange_release", "event_id": "shared-release-O3", "order_id": "O3"},
            ],
        }

        report = audit_db(db)
        codes = {item["code"] for item in report["findings"]}

        self.assertEqual(report["status"], "FAIL")
        self.assertIn("CROSS_LEDGER_EVENT_ID_REQUIRES_REVIEW", codes)
        self.assertIn("MIXED_LEDGER_DOMAINS_REQUIRES_REVIEW", codes)
        self.assertEqual(
            len([item for item in report["findings"]
                 if item["code"] == "CROSS_LEDGER_EVENT_ID_REQUIRES_REVIEW"]),
            2,
        )

    def test_release_in_token_ledger_does_not_balance_credits_ledger_reserve(self):
        db = {
            "exchange_orders": {
                "O4": {"id": "O4", "uid": "42", "side": "sell", "status": "cancelled"}
            },
            "ledger": [
                {"uid": "42", "amount": -100, "reason": "exchange:sell_reserve",
                 "event_id": "reserve:O4", "meta": {"order_id": "O4"}},
            ],
            "slh_token_ledger": [
                {"amount": 100, "reason": "exchange:cancel_release_slh",
                 "kind": "exchange_release", "event_id": "release:O4", "order_id": "O4"},
            ],
        }

        report = audit_db(db)
        codes = {item["code"] for item in report["findings"]}
        delta = next(item for item in report["findings"]
                     if item["code"] == "RESERVE_DELTA_NOT_ZERO")

        self.assertEqual(report["status"], "FAIL")
        self.assertIn("MIXED_LEDGER_DOMAINS_REQUIRES_REVIEW", codes)
        self.assertEqual(delta["ledger"], "ledger")
        self.assertEqual(delta["net_delta"], "-100")

    def test_missing_reserve_event_id_fails_closed_even_if_amounts_balance(self):
        db = {
            "exchange_orders": {
                "O5": {"id": "O5", "uid": "42", "side": "sell", "status": "cancelled"}
            },
            "ledger": [
                {"uid": "42", "amount": -100, "reason": "exchange:sell_reserve",
                 "meta": {"order_id": "O5"}},
                {"uid": "42", "amount": 100, "reason": "exchange:cancel_release",
                 "event_id": "release:O5", "meta": {"order_id": "O5"}},
            ],
            "slh_token_ledger": [],
        }

        report = audit_db(db)
        missing = [item for item in report["findings"]
                   if item["code"] == "LEDGER_EVENT_ID_MISSING"]

        self.assertEqual(report["status"], "FAIL")
        self.assertTrue(any(item["ledger"] == "ledger" and item["order_id"] == "O5"
                            and item["group"] == "reserve" for item in missing))

    def test_non_finite_reserve_amounts_fail_closed(self):
        for amount in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(amount=amount):
                db = {
                    "exchange_orders": {
                        "O6": {"id": "O6", "uid": "42", "side": "sell", "status": "cancelled"}
                    },
                    "ledger": [
                        {"uid": "42", "amount": amount, "reason": "exchange:sell_reserve",
                         "event_id": "reserve:O6", "meta": {"order_id": "O6"}},
                        {"uid": "42", "amount": 100, "reason": "exchange:cancel_release",
                         "event_id": "release:O6", "meta": {"order_id": "O6"}},
                    ],
                    "slh_token_ledger": [],
                }

                report = audit_db(db)
                self.assertEqual(report["status"], "FAIL")
                self.assertIn("INVALID_RESERVE_LEDGER_AMOUNT",
                              {item["code"] for item in report["findings"]})

    def test_duplicate_event_id_within_one_ledger_is_reported(self):
        db = {
            "exchange_orders": {
                "O7": {"id": "O7", "uid": "42", "side": "sell", "status": "cancelled"}
            },
            "ledger": [
                {"uid": "42", "amount": -100, "reason": "exchange:sell_reserve",
                 "event_id": "same-id", "meta": {"order_id": "O7"}},
                {"uid": "42", "amount": -100, "reason": "exchange:sell_reserve",
                 "event_id": "same-id", "meta": {"order_id": "O7"}},
            ],
            "slh_token_ledger": [],
        }

        report = audit_db(db)
        duplicate = next(item for item in report["findings"]
                         if item["code"] == "DUPLICATE_LEDGER_EVENT_ID")

        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(duplicate["ledger"], "ledger")
        self.assertIn("same-id", duplicate["event_ids"])

    def test_duplicate_non_exchange_event_ids_do_not_poison_reserve_audit(self):
        db = {
            "exchange_orders": {},
            "ledger": [
                {
                    "uid": "42",
                    "amount": -10,
                    "reason": "p2p_credits:send",
                    "event_id": "p2p_credits:8789977826:8789977826:195236",
                },
                {
                    "uid": "42",
                    "amount": 10,
                    "reason": "p2p_credits:receive",
                    "event_id": "p2p_credits:8789977826:8789977826:195236",
                },
            ],
            "slh_token_ledger": [],
        }

        report = audit_db(db)
        codes = {item["code"] for item in report["findings"]}

        self.assertEqual(report["status"], "UNKNOWN")
        self.assertNotIn("DUPLICATE_LEDGER_EVENT_ID", codes)


    def test_non_exchange_corrections_without_order_ids_do_not_poison_reserve_audit(self):
        db = {
            "exchange_orders": {},
            "ledger": [
                {"uid": "42", "amount": 0, "reason": "rewards:correction"},
                {"uid": "42", "amount": 0, "kind": "referral_correction"},
                {"uid": "42", "amount": 0, "reason": "profile:manual correction"},
            ],
            "slh_token_ledger": [],
        }

        report = audit_db(db)
        codes = {item["code"] for item in report["findings"]}

        self.assertEqual(report["status"], "UNKNOWN")
        self.assertIn("NO_CANCELLED_SELL_ORDERS_WITH_RESERVE_FOUND", codes)
        self.assertNotIn("LEDGER_EVENT_ID_MISSING", codes)
        self.assertNotIn("ORPHAN_RESERVE_CORRECTION", codes)

    def test_exchange_reserve_correction_without_event_id_still_fails_closed(self):
        db = {
            "exchange_orders": {
                "O8": {"id": "O8", "uid": "42", "side": "sell", "status": "cancelled"}
            },
            "ledger": [
                {"uid": "42", "amount": -100, "reason": "exchange:sell_reserve",
                 "event_id": "reserve:O8", "meta": {"order_id": "O8"}},
                {"uid": "42", "amount": 100, "reason": "exchange:missed_release_correction",
                 "meta": {"order_id": "O8"}},
            ],
            "slh_token_ledger": [],
        }

        report = audit_db(db)
        codes = {item["code"] for item in report["findings"]}
        missing = next(item for item in report["findings"]
                       if item["code"] == "LEDGER_EVENT_ID_MISSING")

        self.assertEqual(report["status"], "FAIL")
        self.assertIn("MANUAL_RESERVE_CORRECTION_REQUIRES_REVIEW", codes)
        self.assertEqual(missing["ledger"], "ledger")
        self.assertEqual(missing["order_id"], "O8")
        self.assertEqual(missing["group"], "correction")


    def test_periodic_audit_logs_all_findings_in_safe_bounded_chunks(self):
        class StopPeriodicLoop(Exception):
            pass

        findings = [
            {
                "code": f"FINDING_{index:02d}",
                "order_id": f"O{index:010d}",
                "ledger": "ledger",
                "event_id": f"event:{index:02d}",
                "uid": "private-full-user-id",
                "note": "private note must not be logged",
            }
            for index in range(23)
        ]
        report = {
            "status": "FAIL",
            "checked_cancelled_sell_orders": 7,
            "finding_count": len(findings),
            "findings": findings,
        }
        messages = []

        with patch.object(reconciliation, "run_once", return_value=report):
            with patch.object(reconciliation.time, "sleep", side_effect=StopPeriodicLoop):
                with self.assertRaises(StopPeriodicLoop):
                    reconciliation.run_periodic(messages.append, interval_seconds=60)

        details = [
            line for line in messages
            if line.startswith("[SLH_EXCHANGE_RECONCILIATION_DETAILS]")
        ]
        self.assertEqual(len(details), 5)
        joined = "\n".join(messages)
        for index in range(23):
            self.assertIn(f"FINDING_{index:02d}", joined)
            self.assertIn(f"event:{index:02d}", joined)
        self.assertIn("finding_count=23", joined)
        self.assertNotIn("private-full-user-id", joined)
        self.assertNotIn("private note must not be logged", joined)
        self.assertTrue(all(len(line) < 4000 for line in details))


    def test_cancelled_buy_credit_release_does_not_poison_sell_reserve_audit(self):
        # This audit proves SLH SELL reserve releases only. A legacy BUY order
        # releases Credits, and must not be mistaken for an SLH reserve event.
        db = {
            "exchange_orders": {
                "O_BUY": {
                    "id": "O_BUY", "uid": "42", "side": "buy",
                    "status": "cancelled", "original_amount": "100",
                    "remaining_amount": "0", "reserved_credits": "0",
                }
            },
            "ledger": [
                {
                    "uid": "42", "amount": 100,
                    "reason": "exchange:cancel_release_credits",
                    "meta": {"order_id": "O_BUY"},
                }
            ],
            "slh_token_ledger": [],
        }

        report = audit_db(db)
        codes = {item["code"] for item in report["findings"]}

        self.assertEqual(report["status"], "UNKNOWN")
        self.assertNotIn("LEDGER_EVENT_ID_MISSING", codes)
        self.assertNotIn("DUPLICATE_LEDGER_EVENT_ID", codes)



    def test_findings_include_sanitized_order_and_wallet_state_for_triage(self):
        db = {
            "users": {
                "seller": {
                    "wallet": {
                        "token_balance": 5.0,
                        "live_token_balance": 5.0,
                        "exchange_reserved_slh": 0.0,
                    }
                }
            },
            "exchange_orders": {
                "O0000000006": {
                    "id": "O0000000006",
                    "uid": "seller",
                    "side": "sell",
                    "status": "cancelled",
                    "original_amount": "5",
                    "remaining_amount": "0",
                    "reserved_slh": "0",
                    "reserved_credits": "0",
                }
            },
            "ledger": [
                {
                    "uid": "seller",
                    "amount": -5,
                    "reason": "exchange:sell_reserve",
                    "meta": {"order_id": "O0000000006"},
                }
            ],
            "slh_token_ledger": [],
        }

        report = audit_db(db)
        finding = next(
            item for item in report["findings"]
            if item["code"] == "CANCELLED_SELL_ORDER_MISSING_NORMAL_RELEASE"
        )

        self.assertEqual(finding["order_status"], "CANCELLED")
        self.assertTrue(finding["order_remaining_is_zero"])
        self.assertTrue(finding["order_reserved_slh_is_zero"])
        self.assertTrue(finding["wallet_reserved_slh_is_zero"])
        self.assertTrue(finding["wallet_reserve_matches_open_orders"])
        self.assertNotIn("uid", finding)
        self.assertNotIn("wallet_exchange_reserved_slh", finding)



    def test_audit_context_classifies_archived_seed_orders_safely(self):
        db = {
            "users": {
                "seller": {
                    "wallet": {
                        "token_balance": 5.0,
                        "live_token_balance": 5.0,
                        "exchange_reserved_slh": 0.0,
                    }
                }
            },
            "exchange_orders": {},
            "exchange_order_archive": {
                "O_TEST_1": {
                    "id": "O_TEST_1",
                    "uid": "seller",
                    "side": "sell",
                    "status": "cancelled",
                    "original_amount": "5",
                    "remaining_amount": "0",
                    "reserved_slh": "0",
                    "reserved_credits": "0",
                    "test": True,
                    "archived_at": "2026-10-13T00:00:00+00:00",
                    "archive_reason": "test_seed_retirement",
                }
            },
            "ledger": [
                {
                    "uid": "seller",
                    "amount": -5,
                    "reason": "exchange:sell_reserve",
                    "event_id": "reserve:O_TEST_1",
                    "meta": {"order_id": "O_TEST_1"},
                }
            ],
            "slh_token_ledger": [],
        }

        report = audit_db(db)
        finding = next(
            item for item in report["findings"]
            if item["code"] == "CANCELLED_SELL_ORDER_MISSING_NORMAL_RELEASE"
        )

        self.assertTrue(finding["order_is_archived"])
        self.assertTrue(finding["order_is_test_seed"])
        self.assertTrue(finding["order_is_archived_test_seed"])
        self.assertNotIn("uid", finding)
        self.assertNotIn("token_balance", finding)
        self.assertNotIn("wallet_reserved_slh", finding)



    def test_archived_test_seed_can_be_operationally_historical_but_block_release(self):
        db = {
            "users": {
                "seller": {"wallet": {
                    "token_balance": 5.0,
                    "live_token_balance": 5.0,
                    "exchange_reserved_slh": 0.0,
                }}
            },
            "exchange_orders": {},
            "exchange_order_archive": {
                "O_TEST_1": {
                    "id": "O_TEST_1", "uid": "seller", "side": "sell",
                    "status": "cancelled", "original_amount": "5",
                    "remaining_amount": "0", "reserved_slh": "0",
                    "reserved_credits": "0", "test": True,
                    "archived_at": "2026-10-13T00:00:00+00:00",
                    "archive_reason": "test_seed_retirement",
                }
            },
            "ledger": [{
                "uid": "seller", "amount": -5,
                "reason": "exchange:sell_reserve", "event_id": "reserve:O_TEST_1",
                "meta": {"order_id": "O_TEST_1"},
            }],
            "slh_token_ledger": [],
        }

        report = audit_db(db)

        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["operational_status"], "PASS")
        self.assertEqual(report["release_readiness_status"], "BLOCKED")
        self.assertGreater(report["release_blocking_finding_count"], 0)
        self.assertEqual(report["blocking_finding_count"], 0)
        self.assertEqual(report["historical_finding_count"], report["finding_count"])
        self.assertEqual(len(report["blocking_findings"]), 0)
        self.assertEqual(len(report["historical_findings"]), report["finding_count"])
        self.assertTrue(all(
            item["operational_classification"] == "HISTORICAL_ARCHIVED_TEST_SEED"
            for item in report["findings"]
        ))

    def test_balanced_legacy_cancel_with_missing_ids_is_nonblocking_only_with_current_state_proof(self):
        db = {
            "users": {
                "seller": {"wallet": {
                    "token_balance": 5.0,
                    "live_token_balance": 5.0,
                    "exchange_reserved_slh": 0.0,
                }}
            },
            "exchange_orders": {
                "O_LEGACY": {
                    "id": "O_LEGACY", "uid": "seller", "side": "sell",
                    "status": "cancelled", "original_amount": "5",
                    "remaining_amount": "0", "reserved_slh": "0",
                    "reserved_credits": "0",
                }
            },
            "ledger": [
                {
                    "uid": "seller", "amount": -5,
                    "reason": "exchange:sell_reserve",
                    "meta": {"order_id": "O_LEGACY"},
                },
                {
                    "uid": "seller", "amount": 5,
                    "reason": "exchange:cancel_release",
                    "meta": {"order_id": "O_LEGACY"},
                },
            ],
            "slh_token_ledger": [],
        }

        report = audit_db(db)

        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["operational_status"], "PASS")
        self.assertEqual(report["release_readiness_status"], "PASS")
        self.assertEqual(report["release_blocking_finding_count"], 0)
        self.assertGreater(report["historical_finding_count"], 0)
        self.assertEqual(report["blocking_finding_count"], 0)
        self.assertTrue(all(
            item["operational_classification"] == "LEGACY_BALANCED_CANCELLED_ORDER"
            for item in report["findings"]
        ))
        self.assertTrue(all(
            item["code"] == "LEDGER_EVENT_ID_MISSING"
            for item in report["findings"]
        ))

    def test_unbalanced_nonseed_cancelled_sell_reserve_remains_blocking(self):
        db = {
            "users": {
                "seller": {"wallet": {
                    "token_balance": 5.0,
                    "live_token_balance": 5.0,
                    "exchange_reserved_slh": 0.0,
                }}
            },
            "exchange_orders": {
                "O_UNBALANCED": {
                    "id": "O_UNBALANCED", "uid": "seller", "side": "sell",
                    "status": "cancelled", "original_amount": "5",
                    "remaining_amount": "0", "reserved_slh": "0",
                    "reserved_credits": "0",
                }
            },
            "ledger": [{
                "uid": "seller", "amount": -5,
                "reason": "exchange:sell_reserve", "event_id": "reserve:O_UNBALANCED",
                "meta": {"order_id": "O_UNBALANCED"},
            }],
            "slh_token_ledger": [],
        }

        report = audit_db(db)

        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["operational_status"], "BLOCKED")
        self.assertEqual(report["release_readiness_status"], "BLOCKED")
        self.assertGreater(report["release_blocking_finding_count"], 0)
        self.assertGreater(report["blocking_finding_count"], 0)
        self.assertGreater(len(report["blocking_findings"]), 0)
        self.assertTrue(any(
            item["code"] == "CANCELLED_SELL_ORDER_MISSING_NORMAL_RELEASE"
            for item in report["blocking_findings"]
        ))

    def test_archived_test_seed_is_blocking_if_current_wallet_reserve_is_inconsistent(self):
        db = {
            "users": {
                "seller": {"wallet": {
                    "token_balance": 5.0,
                    "live_token_balance": 5.0,
                    "exchange_reserved_slh": 2.0,
                }}
            },
            "exchange_orders": {},
            "exchange_order_archive": {
                "O_TEST_2": {
                    "id": "O_TEST_2", "uid": "seller", "side": "sell",
                    "status": "cancelled", "original_amount": "5",
                    "remaining_amount": "0", "reserved_slh": "0",
                    "reserved_credits": "0", "test": True,
                    "archived_at": "2026-10-13T00:00:00+00:00",
                    "archive_reason": "test_seed_retirement",
                }
            },
            "ledger": [{
                "uid": "seller", "amount": -5,
                "reason": "exchange:sell_reserve", "event_id": "reserve:O_TEST_2",
                "meta": {"order_id": "O_TEST_2"},
            }],
            "slh_token_ledger": [],
        }

        report = audit_db(db)

        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["operational_status"], "BLOCKED")
        self.assertEqual(report["release_readiness_status"], "BLOCKED")
        self.assertGreater(report["release_blocking_finding_count"], 0)
        self.assertGreater(report["blocking_finding_count"], 0)
        self.assertTrue(any(
            item.get("wallet_reserve_matches_open_orders") is False
            for item in report["blocking_findings"]
        ))


    def test_archived_test_seed_manual_correction_still_blocks_public_release(self):
        order_id = "O0000000009"
        event_id = f"correction:missed_release:{order_id}"
        db = {
            "users": {
                "seller": {"wallet": {
                    "token_balance": 50000.0,
                    "exchange_reserved_slh": 0.0,
                }}
            },
            "exchange_orders": {},
            "exchange_order_archive": {
                order_id: {
                    "id": order_id,
                    "uid": "seller",
                    "side": "sell",
                    "status": "cancelled",
                    "original_amount": "10000",
                    "remaining_amount": "0",
                    "reserved_slh": "0",
                    "reserved_credits": "0",
                    "test": True,
                    "archive_reason": "test_seed_retirement",
                    "archived_at": "2026-09-28T00:00:00+00:00",
                }
            },
            "exchange_trades": [],
            "ledger": [
                {
                    "uid": "seller", "amount": -10000.0,
                    "reason": "exchange:sell_reserve",
                    "event_id": f"reserve:{order_id}",
                    "meta": {"order_id": order_id},
                },
                {
                    "uid": "seller", "amount": 10000.0,
                    "reason": "exchange:missed_release_correction",
                    "event_id": event_id,
                    "meta": {"order_id": order_id, "event_id": event_id},
                },
            ],
            "slh_token_ledger": [{
                "amount": 10000.0,
                "reason": "exchange:missed_release_correction",
                "kind": "reserve_release_correction",
                "event_id": event_id,
                "order_id": order_id,
            }],
        }

        report = audit_db(db)

        self.assertEqual(report["operational_status"], "PASS")
        self.assertEqual(report["release_readiness_status"], "BLOCKED")
        self.assertGreater(report["release_blocking_finding_count"], 0)
        self.assertTrue(any(
            item.get("code") == "MANUAL_RESERVE_CORRECTION_REQUIRES_REVIEW"
            and item.get("order_id") == order_id
            for item in report["release_blocking_findings"]
        ))

if __name__ == "__main__":
    unittest.main()
