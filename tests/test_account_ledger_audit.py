from copy import deepcopy

from core.account_ledger_audit import audit_account_ledger


UID = "owner-1"


def _db():
    return {
        "users": {UID: {"wallet": {"credits": 3.0}}},
        "ledger": [
            {"uid": UID, "before": 1.0, "amount": 2.0, "after": 3.0,
             "reason": "store:purchase", "meta": {"event_id": "e1"}},
            {"uid": "someone-else", "before": 100.0, "amount": -1.0, "after": 99.0,
             "reason": "other"},
            {"uid": UID, "before": 7.0, "amount": 1.0, "after": 8.0,
             "reason": "exchange:sell_reserve", "meta": {"order_id": "O-1", "ledger_domain": "slh"}},
        ],
    }


def test_audit_does_not_compare_slh_rows_as_credits_without_mutation():
    db = _db()
    before = deepcopy(db)

    result = audit_account_ledger(db, UID)

    assert result["scope"] == "read_only"
    assert result["status"] == "PASS"
    assert result["rows_checked"] == 2
    assert result["credits_sequence_rows_checked"] == 1
    assert result["non_credits_rows_skipped"] == 1
    assert result["continuity_break_count"] == 0
    assert result["arithmetic_error_count"] == 0
    assert result["current_balance_matches_tail"] is True
    assert result["domain_hints_are_authoritative"] is False
    assert result["financial_mutation_performed"] is False
    assert result["gate_changed"] is False
    assert db == before


def test_credits_sequence_continues_across_interleaved_slh_rows():
    db = {
        "users": {UID: {"wallet": {"credits": 90.0}}},
        "ledger": [
            {"uid": UID, "before": 100.0, "amount": -5.0, "after": 95.0,
             "reason": "store:purchase"},
            {"uid": UID, "before": 2000.0, "amount": -1000.0, "after": 1000.0,
             "reason": "exchange:sell_reserve", "meta": {"ledger_domain": "slh"}},
            {"uid": UID, "before": 95.0, "amount": -5.0, "after": 90.0,
             "reason": "store:purchase"},
        ],
    }

    result = audit_account_ledger(db, UID)

    assert result["status"] == "PASS"
    assert result["credits_sequence_rows_checked"] == 2
    assert result["non_credits_rows_skipped"] == 1
    assert result["continuity_break_count"] == 0
    assert result["current_balance_matches_tail"] is True




def test_canonical_slh_reason_without_metadata_is_excluded_from_credits_sequence():
    db = {
        "users": {UID: {"wallet": {"credits": 90.0}}},
        "ledger": [
            {"uid": UID, "before": 100.0, "amount": -5.0, "after": 95.0,
             "reason": "store:purchase", "meta": {"ledger_domain": "credits"}},
            {"uid": UID, "before": 2000.0, "amount": -1000.0, "after": 1000.0,
             "reason": "exchange:sell_reserve"},
            {"uid": UID, "before": 95.0, "amount": -5.0, "after": 90.0,
             "reason": "store:purchase", "meta": {"ledger_domain": "credits"}},
        ],
    }

    result = audit_account_ledger(db, UID)

    assert result["status"] == "PASS"
    assert result["credits_sequence_rows_checked"] == 2
    assert result["non_credits_rows_skipped"] == 1
    assert result["continuity_break_count"] == 0
    assert result["current_balance_matches_tail"] is True


def test_unknown_slh_like_reason_remains_ambiguous_and_blocks():
    from core.account_ledger_audit import _row_domain_hint

    row = {
        "reason": "slh:legacy_unverified",
        "before": 2000.0, "amount": -1000.0, "after": 1000.0,
    }
    assert _row_domain_hint(row) == "AMBIGUOUS_DOMAIN_HINT"


def test_same_unknown_domain_gap_still_blocks_account_audit():
    db = _db()
    db["ledger"][2]["reason"] = "store:p2p_sale"
    # This test is specifically for an unknown domain, not explicit SLH metadata.
    db["ledger"][2].pop("meta", None)
    db["ledger"][2]["before"] = 7.0
    db["ledger"][2]["amount"] = 1.0
    db["ledger"][2]["after"] = 8.0
    db["users"][UID]["wallet"]["credits"] = 8.0

    result = audit_account_ledger(db, UID)

    assert result["continuity_break_count"] == 1
    assert result["status"] == "BLOCKED"
    assert result["findings"][0]["type"] == "SEQUENCE_GAP_REQUIRES_SOURCE_EVIDENCE"


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



def test_staked_counter_row_without_authoritative_domain_marker_stays_blocked():
    from core.account_ledger_audit import _row_domain_hint

    db = {
        "users": {UID: {"wallet": {"credits": 5.0}}},
        "ledger": [
            {
                "uid": UID,
                "before": 100.0,
                "amount": -100.0,
                "after": 0.0,
                "reason": "admin_correction_unbacked_test_credits_release",
                "meta": {"ledger_domain": "credits"},
            },
            {
                "uid": UID,
                "before": 552.0,
                "amount": 0.0,
                "after": 552.0,
                "reason": "reconciliation:staked_counter_fix",
                "meta": {
                    "ref": "RECON-240-20260919",
                    "staked_before": 552.0,
                    "staked_after": 792.0,
                    "note": "counter resync to ledger-proven locked total; no credits minted",
                },
            },
            {
                "uid": UID,
                "before": 0.0,
                "amount": 5.0,
                "after": 5.0,
                "reason": "store:purchase",
                "meta": {"ledger_domain": "credits"},
            },
        ],
    }

    assert _row_domain_hint(db["ledger"][1]) == "STAKED_COUNTER_HINT"
    result = audit_account_ledger(db, UID)
    # Skipping the proven counter-only row preserves the adjacent Credits
    # sequence (0 -> 5) without treating the staking counter as a wallet balance.
    assert result["status"] == "PASS"
    assert result["continuity_break_count"] == 0

def test_gap_shows_linked_transfer_and_purchase_context_without_resolving_gap():
    db = {
        "users": {UID: {"wallet": {"credits": 7.091775}}},
        "processed_transfers": {
            "TG-TRANSFER-owner-191058": "TRANSFER-20261005145750197186",
        },
        "purchases": {
            "purchase:telegram_buy:buyer:191618": {
                "purchase_id": "purchase:telegram_buy:buyer:191618",
                "request_id": "telegram_buy:buyer:191618",
                "uid": "buyer",
                "seller_uid": UID,
                "item_id": "market_smoke",
                "price": 1.0,
                "seller_payout": 0.9,
                "commission": 0.1,
                "status": "FULFILLED",
                "created_at": "2026-10-05T16:19:45.915817+00:00",
            },
        },
        "ledger": [
            {
                "time": "2026-10-05T14:57:50+00:00",
                "uid": UID,
                "before": 2.191775,
                "amount": -1.0,
                "after": 1.191775,
                "reason": "p2p:transfer_sent",
                "meta": {
                    "transfer_id": "TRANSFER-20261005145750197186",
                    "recipient_uid": "buyer",
                },
            },
            {
                "time": "2026-10-05T14:57:50+00:00",
                "uid": "buyer",
                "before": 0.0,
                "amount": 1.0,
                "after": 1.0,
                "reason": "p2p:transfer_received",
                "meta": {
                    "transfer_id": "TRANSFER-20261005145750197186",
                    "sender_uid": UID,
                },
            },
            {
                "time": "2026-10-05T16:19:45+00:00",
                "uid": "buyer",
                "before": 1.0,
                "amount": -1.0,
                "after": 0.0,
                "reason": "store:p2p_purchase",
                "meta": {
                    "purchase_id": "purchase:telegram_buy:buyer:191618",
                    "seller_uid": UID,
                },
            },
            {
                "time": "2026-10-05T16:19:45+00:00",
                "uid": UID,
                "before": 6.191775,
                "amount": 0.9,
                "after": 7.091775,
                "reason": "store:p2p_sale",
                "meta": {
                    "purchase_id": "purchase:telegram_buy:buyer:191618",
                    "buyer_uid": "buyer",
                },
            },
        ],
    }

    result = audit_account_ledger(db, UID)

    assert result["status"] == "BLOCKED"
    assert result["continuity_break_count"] == 1
    finding = result["findings"][0]
    assert finding["delta_to_explain"] == 5.0
    evidence = finding["source_evidence"]
    assert evidence["resolves_gap"] is False
    assert evidence["source_match_status"] == "CONTEXT_ONLY_REQUIRES_RECONCILIATION"
    assert evidence["transfer"]["record_found"] is True
    assert len(evidence["transfer"]["ledger_rows"]) == 2
    assert evidence["transfer"]["processed_keys"] == ["TG-TRANSFER-owner-191058"]
    assert evidence["purchase"]["record_found"] is True
    assert evidence["purchase"]["status"] == "FULFILLED"
    assert evidence["purchase"]["seller_payout"] == 0.9

def test_verified_historical_alpha_consolidation_resolves_only_its_exact_credits_gap():
    target_uid = "8789977826"
    source_uid = "8791275334"
    db = {
        "users": {
            target_uid: {"wallet": {"credits": 11715.0, "staked": 794.0}},
            source_uid: {"wallet": {"credits": 0.0, "staked": 0.0}},
        },
        "ledger": [
            {"time": "2026-08-20T14:18:40.628968+00:00", "uid": target_uid,
             "before": 1314.0, "amount": 1.0, "after": 1315.0,
             "reason": "P0_AUTHORITY_VERIFY"},
            {"time": "2026-08-20T14:18:59.208393+00:00", "uid": target_uid,
             "before": 1315.0, "amount": 1.0, "after": 1316.0,
             "reason": "P0_AUTHORITY_VERIFY"},
            {"time": "2026-08-22T16:12:41.978584+00:00", "type": "alpha_consolidate",
             "from": source_uid, "to": target_uid, "credits": 10449,
             "staked_moved": 50, "reason": "OWNER_ONLY_CREDITS_POLICY"},
            {"time": "2026-08-25T14:20:44.705458+00:00", "uid": target_uid,
             "before": 11815.0, "amount": -100.0, "after": 11715.0,
             "reason": "staking:stake",
             "meta": {"staked_before": 136, "staked_after": 236}},
        ],
    }
    before = deepcopy(db)

    result = audit_account_ledger(db, target_uid)

    assert result["status"] == "PASS"
    assert result["continuity_break_count"] == 0
    assert result["observed_discontinuity_count"] == 1
    assert result["resolved_gap_count"] == 1
    assert result["blocking_finding_count"] == 0
    assert result["current_balance_matches_tail"] is True
    finding = result["findings"][0]
    assert finding["type"] == "RECONCILED_ALPHA_CONSOLIDATION"
    assert finding["reconciled"] is True
    evidence = finding["source_evidence"]
    assert evidence["source_match_status"] == "VERIFIED_HISTORICAL_ALPHA_CONSOLIDATION"
    assert evidence["resolves_gap"] is True
    consolidation = evidence["alpha_consolidations"][0]
    assert consolidation["credits_component"] == 10449
    assert consolidation["staked_moved_component"] == 50
    assert consolidation["observed_balance_delta"] == 10499
    assert consolidation["credits_plus_staked_matches_delta"] is True
    assert consolidation["source_commit"] == "d013b914bbca1b6c2f50e768d461213ae1cbfbef"
    assert db == before


def test_unverified_alpha_consolidation_near_miss_stays_blocked():
    target_uid = "8789977826"
    db = {
        "users": {target_uid: {"wallet": {"credits": 11715.0}}},
        "ledger": [
            {"uid": target_uid, "before": 1315.0, "amount": 1.0, "after": 1316.0,
             "reason": "P0_AUTHORITY_VERIFY"},
            {"time": "2026-08-22T16:12:41.978584+00:00", "type": "alpha_consolidate",
             "from": "different-source", "to": target_uid, "credits": 10449,
             "staked_moved": 50, "reason": "OWNER_ONLY_CREDITS_POLICY"},
            {"uid": target_uid, "before": 11815.0, "amount": -100.0, "after": 11715.0,
             "reason": "staking:stake"},
        ],
    }

    result = audit_account_ledger(db, target_uid)

    assert result["status"] == "BLOCKED"
    assert result["continuity_break_count"] == 1
    assert result["resolved_gap_count"] == 0
    assert result["findings"][0]["reconciled"] is False
    assert result["findings"][0]["source_evidence"]["resolves_gap"] is False
