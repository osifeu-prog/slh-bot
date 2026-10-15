from copy import deepcopy

from core.account_ledger_audit import audit_account_ledger


UID = "owner-1"


def _db():
    return {
        "users": {UID: {"wallet": {"credits": 8.0}}},
        "ledger": [
            {"uid": UID, "before": 1.0, "amount": 2.0, "after": 3.0,
             "reason": "store:purchase", "meta": {"event_id": "e1"}},
            {"uid": "someone-else", "before": 100.0, "amount": -1.0, "after": 99.0,
             "reason": "other"},
            {"uid": UID, "before": 7.0, "amount": 1.0, "after": 8.0,
             "reason": "exchange:sell_reserve", "meta": {"order_id": "O-1"}},
        ],
    }


def test_audit_reports_continuity_gap_and_heuristic_mixed_domain_without_mutation():
    db = _db()
    before = deepcopy(db)

    result = audit_account_ledger(db, UID)

    assert result["scope"] == "read_only"
    assert result["status"] == "BLOCKED"
    assert result["rows_checked"] == 2
    assert result["continuity_break_count"] == 1
    assert result["arithmetic_error_count"] == 0
    assert result["current_balance_matches_tail"] is True
    assert result["findings"][0]["type"] == "POSSIBLE_MIXED_DOMAIN_BOUNDARY"
    assert result["findings"][0]["source_evidence_required"] is True
    assert result["domain_hints_are_authoritative"] is False
    assert result["financial_mutation_performed"] is False
    assert result["gate_changed"] is False
    assert db == before


def test_audit_separates_row_arithmetic_errors_from_sequence_gaps():
    db = _db()
    db["ledger"][0]["after"] = 99.0

    result = audit_account_ledger(db, UID)

    assert result["arithmetic_error_count"] == 1
    assert result["continuity_break_count"] == 0
    assert "ROW_ARITHMETIC_INVALID" in result["blockers"]


def test_audit_reports_wallet_tail_mismatch():
    db = _db()
    db["ledger"] = [db["ledger"][0]]
    db["users"][UID]["wallet"]["credits"] = 4.0

    result = audit_account_ledger(db, UID)

    assert result["current_balance_matches_tail"] is False
    assert result["status"] == "BLOCKED"
    assert "WALLET_BALANCE_DIFFERS_FROM_LEDGER_TAIL" in result["blockers"]


def test_audit_fails_closed_for_malformed_global_rows():
    db = _db()
    db["ledger"].append("malformed")

    result = audit_account_ledger(db, UID)

    assert result["malformed_global_rows"] == 1
    assert "MALFORMED_GLOBAL_LEDGER_ROW" in result["blockers"]


def test_audit_fails_closed_for_missing_uid_or_ledger():
    assert audit_account_ledger({}, "")["blockers"] == ["UID_MISSING"]
    assert audit_account_ledger({"users": {}}, UID)["blockers"] == ["LEDGER_UNREADABLE"]

def test_ambiguous_legacy_reasons_are_not_assigned_a_financial_domain():
    from core.account_ledger_audit import _reason_domain_hint

    assert _reason_domain_hint("airdrop") == "UNKNOWN_HINT"
    assert _reason_domain_hint("bridge:spend") == "UNKNOWN_HINT"
    assert _reason_domain_hint("arcade:entry") == "UNKNOWN_HINT"
    assert _reason_domain_hint("admin:test_grant") == "UNKNOWN_HINT"
