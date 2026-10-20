from copy import deepcopy
from decimal import Decimal
from unittest.mock import patch

import pytest
import state_manager
from core.trader_certification import (
    REFERRAL_PROMO_KEY,
    TRADER_COURSE_ID,
    TRADER_QUIZ_VERSION,
    award_referral_course,
    has_trader_certification,
)

def _user():
    return {"academy": {"courses": {}}, "referral": {}, "wallet": {
        "credits": 100, "token_balance": 10, "live_token_balance": 10,
        "exchange_reserved_slh": 0, "exchange_reserved_credits": 0,
    }}

def _install_db(monkeypatch, db):
    monkeypatch.setattr(state_manager, "load_db", lambda: db)
    monkeypatch.setattr(state_manager, "atomic_update", lambda mutate: mutate(db))

def test_first_fifteen_unique_verified_referrers_receive_one_free_course(monkeypatch):
    users = {}
    for referrer in range(1, 17):
        users[str(referrer)] = _user()
        referred = str(1000 + referrer)
        users[referred] = _user()
        users[referred]["referral"]["referred_by"] = str(referrer)
    db = {"users": users}
    _install_db(monkeypatch, db)

    for referrer in range(1, 16):
        result = award_referral_course(str(referrer), str(1000 + referrer), now="2026-10-16T00:00:00+00:00")
        assert result["status"] == "GRANTED"
        assert result["award"]["slot"] == referrer
        progress = users[str(referrer)]["academy"]["courses"][TRADER_COURSE_ID]
        assert progress["access_grant"] == "verified_referral_first15"
        assert progress["completed"] == []

    over_limit = award_referral_course("16", "1016", now="2026-10-16T00:00:00+00:00")
    assert over_limit["status"] == "PROMO_FULL"
    campaign = db[REFERRAL_PROMO_KEY]
    assert len(campaign["awards"]) == 15
    assert TRADER_COURSE_ID not in users["16"]["academy"]["courses"]

def test_promo_requires_real_persisted_referral_and_is_idempotent(monkeypatch):
    users = {"1": _user(), "2": _user(), "3": _user()}
    users["2"]["referral"]["referred_by"] = "1"
    users["3"]["referral"]["referred_by"] = "1"
    db = {"users": users}
    _install_db(monkeypatch, db)

    first = award_referral_course("1", "2")
    second = award_referral_course("1", "3")
    no_relationship = award_referral_course("3", "2")

    assert first["status"] == "GRANTED"
    assert second["status"] == "ALREADY_AWARDED"
    assert no_relationship["status"] == "INELIGIBLE"
    assert len(db[REFERRAL_PROMO_KEY]["awards"]) == 1

def test_certification_requires_server_record_and_all_seven_completed_lessons():
    user = _user()
    db = {
        "users": {"1": user},
        "trader_certifications": {
            "1": {
                "passed": True,
                "score": 9,
                "critical_pass": True,
                "quiz_version": TRADER_QUIZ_VERSION,
            }
        },
    }
    user["academy"]["courses"][TRADER_COURSE_ID] = {"stage": 7, "completed": [1, 2, 3, 4, 5, 6, 7]}
    assert has_trader_certification("1", db) is True
    user["academy"]["courses"][TRADER_COURSE_ID]["completed"] = [1, 2, 3, 4, 5, 6]
    assert has_trader_certification("1", db) is False
    user["academy"]["courses"][TRADER_COURSE_ID]["completed"] = [1, 2, 3, 4, 5, 6, 7]
    db["trader_certifications"]["1"]["critical_pass"] = False
    assert has_trader_certification("1", db) is False

def test_uncertified_user_is_checked_after_live_exchange_probe(monkeypatch):
    import handlers.exchange_handler as exchange_handler
    db = {
        "users": {"1": _user()},
        "exchange_orders": {},
        "exchange_trades": [],
        "exchange_requests": {},
        "exchange_sequence": 0,
        "ledger": [],
        "slh_token_ledger": [],
    }
    _install_db(monkeypatch, db)
    before = deepcopy(db)
    with patch.object(
        exchange_handler,
        "require_fresh_live_exchange_proof",
        return_value={
            "status": "PASS",
            "checked_at": "2026-10-20T11:00:00+00:00",
            "railway_configured": "1",
            "public_gate": "OPEN",
            "public_verdict": "OPEN",
            "public_readiness": True,
            "public_updated_at": 1792494000.0,
        },
    ) as live_check:
        with pytest.raises(ValueError, match="TRADER_CERTIFICATION_REQUIRED"):
            exchange_handler.execute_exchange_order(
                uid="1", side="buy", amount=Decimal("1"), price=Decimal("1"), request_id="first"
            )
    live_check.assert_called_once()
    assert db == before

def test_atomic_place_boundary_blocks_uncertified_legacy_caller_without_mutation():
    import handlers.exchange_handler as exchange_handler
    db = {
        "users": {"1": _user()},
        "exchange_orders": {},
        "exchange_trades": [],
        "exchange_requests": {},
        "exchange_sequence": 0,
        "ledger": [],
        "slh_token_ledger": [],
    }
    before = deepcopy(db)
    with pytest.raises(ValueError, match="TRADER_CERTIFICATION_REQUIRED"):
        exchange_handler._place(db, "1", "buy", Decimal("1"), Decimal("1"), "direct-call")
    assert db == before

def test_test_definition_has_ten_questions_and_safety_critical_items():
    from handlers.trader_certification_handler import QUESTIONS
    assert len(QUESTIONS) == 10
    assert all(question["critical"] for question in QUESTIONS[:4])
    assert all("options" in question and len(question["options"]) == 3 for question in QUESTIONS)
