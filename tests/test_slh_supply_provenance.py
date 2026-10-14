from copy import deepcopy

from core.slh_supply_provenance import audit_db


def test_audit_is_read_only_and_empty_ledger_does_not_invent_supply():
    db = {"users": {}, "ledger": [], "slh_token_ledger": []}
    before = deepcopy(db)

    result = audit_db(db)

    assert result["status"] == "PASS"
    assert result["mint_event_count"] == 0
    assert result["mint_recorded_total"] == "0"
    assert db == before


def test_mint_bootstrap_without_snapshots_and_zero_current_balance_fails_closed():
    db = {
        "users": {
            "owner": {"wallet": {"token_balance": 0, "live_token_balance": 0}},
        },
        "ledger": [],
        "slh_token_ledger": [{
            "timestamp": "2026-09-09T18:06:29+00:00",
            "event_id": "bootstrap-owner",
            "from_uid": "mint",
            "to_uid": "owner",
            "amount": 22000000,
            "reason": "owner_issuance_bootstrap",
            "before_to": None,
            "after_to": None,
        }],
    }

    result = audit_db(db)
    codes = {finding["code"] for finding in result["findings"]}

    assert result["status"] == "FAIL"
    assert result["mint_event_count"] == 1
    assert result["mint_recorded_total"] == "22000000"
    assert "MINT_SOURCE_REQUIRES_RECONCILIATION" in codes
    assert "MINT_BALANCE_SNAPSHOT_MISSING" in codes
    assert "TOKEN_BALANCE_CURRENT_MISMATCH" in codes


def test_sequence_gap_between_recorded_balances_blocks_launch():
    db = {
        "users": {"u": {"wallet": {"token_balance": 5, "live_token_balance": 0}}},
        "ledger": [],
        "slh_token_ledger": [
            {
                "timestamp": "2026-09-01T00:00:00+00:00",
                "event_id": "first",
                "from_uid": "u", "to_uid": "other",
                "amount": 10, "reason": "transfer",
                "before_from": 100, "after_from": 90,
            },
            {
                "timestamp": "2026-09-02T00:00:00+00:00",
                "event_id": "second",
                "from_uid": "u", "to_uid": "other",
                "amount": 5, "reason": "transfer",
                "before_from": 10, "after_from": 5,
            },
        ],
    }

    result = audit_db(db)

    assert result["status"] == "FAIL"
    gap = next(f for f in result["findings"] if f["code"] == "TOKEN_BALANCE_SEQUENCE_GAP")
    assert gap["uid_suffix"] == "u"
    assert gap["gap"] == "-80"


def test_unbacked_test_allocation_still_in_internal_wallet_is_reported():
    db = {
        "users": {
            "recipient": {"wallet": {"token_balance": 50000, "live_token_balance": 0}},
        },
        "ledger": [],
        "slh_token_ledger": [{
            "timestamp": "2026-09-22T16:44:43+00:00",
            "event_id": "test-distribution",
            "from_uid": "owner",
            "to_uid": "recipient",
            "amount": 50000,
            "reason": "unbacked_test_distribution_20260922",
            "before_from": 200000,
            "after_from": 150000,
            "before_to": 0,
            "after_to": 50000,
        }],
    }

    result = audit_db(db)
    codes = {finding["code"] for finding in result["findings"]}

    assert result["status"] == "FAIL"
    assert "UNBACKED_TEST_DISTRIBUTION_REQUIRES_REVIEW" in codes
    outstanding = next(f for f in result["findings"] if f["code"] == "UNBACKED_TEST_BALANCE_OUTSTANDING")
    assert outstanding["outstanding_internal_slh"] == "50000"


def test_current_wallet_must_match_last_reconstructed_token_balance():
    db = {
        "users": {"u": {"wallet": {"token_balance": 0, "live_token_balance": 0}}},
        "ledger": [],
        "slh_token_ledger": [{
            "timestamp": "2026-09-01T00:00:00+00:00",
            "event_id": "legacy-transfer",
            "from_uid": "owner", "to_uid": "u",
            "amount": 10, "reason": "wallet_transfer",
            "before_to": 0, "after_to": 10,
        }],
    }

    result = audit_db(db)

    assert result["status"] == "FAIL"
    mismatch = next(f for f in result["findings"] if f["code"] == "TOKEN_BALANCE_CURRENT_MISMATCH")
    assert mismatch["uid_suffix"] == "u"
    assert mismatch["ledger_expected_balance"] == "10"
    assert mismatch["current_wallet_balance"] == "0"


def test_cross_ledger_correction_is_counted_once_for_balance_continuity():
    db = {
        "users": {"u": {"wallet": {"token_balance": 50, "live_token_balance": 0}}},
        "ledger": [{
            "uid": "u", "time": "2026-09-28T12:00:00+00:00",
            "before": 40, "amount": 10, "after": 50,
            "reason": "exchange:missed_release_correction",
            "meta": {"event_id": "correction-1", "order_id": "O1"},
        }],
        "slh_token_ledger": [{
            "timestamp": "2026-09-28T12:00:00+00:00",
            "event_id": "correction-1", "from_uid": "__EXCHANGE_RESERVE__",
            "to_uid": "u", "amount": 10, "reason": "exchange:missed_release_correction",
            "kind": "reserve_release_correction", "before_to": 40, "after_to": 50,
        }],
    }

    result = audit_db(db)

    gaps = [f for f in result["findings"] if f["code"] == "TOKEN_BALANCE_SEQUENCE_GAP"]
    mismatches = [f for f in result["findings"] if f["code"] == "TOKEN_BALANCE_CURRENT_MISMATCH"]
    assert gaps == []
    assert mismatches == []
