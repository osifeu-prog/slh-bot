from copy import deepcopy

from core.recovery_center import _gap_blocker, build_recovery_center_report


def test_gap_fingerprint_is_stable_and_action_is_evidence_gated():
    finding = {
        "type": "SEQUENCE_GAP_REQUIRES_SOURCE_EVIDENCE",
        "previous": {"index": 10, "reason": "exchange:settlement_credits", "after": 5.0},
        "next": {"index": 12, "reason": "p2p:transfer_sent", "before": 7.0},
        "delta_to_explain": 2.0,
        "source_evidence": {"source_match_status": "NO_DIRECT_SOURCE_MATCH"},
    }

    first = _gap_blocker(finding)
    second = _gap_blocker(deepcopy(finding))

    assert first["id"] == second["id"]
    assert first["status"] == "BLOCKED"
    assert first["automatic_fix"] == "NOT_SAFE_WITHOUT_SOURCE_EVIDENCE"
    assert first["human_action_required"] is True
    assert "synthetic ledger row" in first["next_action"]


def test_gap_fingerprint_changes_when_observed_gap_changes():
    base = {
        "type": "SEQUENCE_GAP_REQUIRES_SOURCE_EVIDENCE",
        "previous": {"index": 10, "reason": "exchange:settlement_credits"},
        "next": {"index": 12, "reason": "p2p:transfer_sent"},
        "delta_to_explain": 2.0,
    }
    changed = deepcopy(base)
    changed["delta_to_explain"] = 3.0

    assert _gap_blocker(base)["id"] != _gap_blocker(changed)["id"]


def test_recovery_center_is_read_only_and_separates_bnb_review_from_ledger_blocker(monkeypatch):
    import core.authority as authority

    monkeypatch.setattr(authority, "OWNER_ID", "8789977826")
    db = {
        "users": {
            "8789977826": {"wallet": {"credits": 8.0}}
        },
        "ledger": [
            {"uid": "8789977826", "time": "2026-01-01T00:00:00Z",
             "reason": "store:purchase", "before": 0, "amount": 5, "after": 5},
            {"uid": "8789977826", "time": "2026-01-01T00:01:00Z",
             "reason": "store:purchase", "before": 7, "amount": 1, "after": 8},
        ],
    }
    before = deepcopy(db)
    release = {
        "overall_status": "BLOCKED",
        "checks": {
            "Internal exchange": {
                "status": "BLOCKED",
                "detail": "account_ledger=BLOCKED(ACCOUNT_LEDGER_SEQUENCE_DISCONTINUITY)",
            },
            "External settlement gates": {
                "status": "DEGRADED",
                "detail": "BNB empirical settlement evidence is revalidated, but the public gate remains CLOSED",
            },
        },
        "blockers": ["Internal exchange blocked"],
    }

    result = build_recovery_center_report(release_report=release, db=db)

    assert db == before
    assert result["mode"] == "READ_ONLY"
    assert result["overall_status"] == "BLOCKED"
    assert result["blockers"]
    assert result["blockers"][0]["automatic_fix"] == "NOT_SAFE_WITHOUT_SOURCE_EVIDENCE"
    assert result["review_items"][0]["id"] == "BNB-OPERATOR-GATE-REVIEW"
    assert "NEVER_OPEN_GATE_AUTOMATICALLY" == result["review_items"][0]["automatic_fix"]
    assert result["persistence"].startswith("Finding IDs are deterministic")
