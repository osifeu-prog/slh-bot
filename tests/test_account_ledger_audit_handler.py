from types import SimpleNamespace
from unittest.mock import patch

from handlers import system_checks_handler as target


OWNER_UID = "8789977826"


class FakeBot:
    def __init__(self):
        self.handlers = {}
        self.replies = []

    def message_handler(self, commands=None, **_kwargs):
        def decorate(function):
            for command in commands or []:
                self.handlers[command] = function
            return function
        return decorate

    def reply_to(self, _message, text, **_kwargs):
        self.replies.append(str(text))


def _message(text="/check_owner_ledger", *, uid=OWNER_UID, chat_type="private"):
    return SimpleNamespace(
        from_user=SimpleNamespace(id=int(uid)),
        chat=SimpleNamespace(type=chat_type),
        text=text,
    )


def _register(monkeypatch, *, owner_uid=OWNER_UID):
    monkeypatch.setattr(target, "is_owner", lambda uid: str(uid) == owner_uid)
    bot = FakeBot()
    target.register(bot)
    return bot


def test_owner_ledger_command_reports_only_the_private_owner_scope(monkeypatch):
    bot = _register(monkeypatch)
    result = {
        "scope": "read_only",
        "status": "BLOCKED",
        "rows_checked": 141,
        "continuity_break_count": 12,
        "arithmetic_error_count": 0,
        "malformed_global_rows": 0,
        "current_wallet_credits": 30.072775,
        "ledger_tail_after": 30.072775,
        "current_balance_matches_tail": True,
        "findings": [{
            "type": "POSSIBLE_MIXED_DOMAIN_BOUNDARY",
            "previous": {"index": 116, "reason": "exchange:sell_reserve",
                         "domain_hint": "SLH_HINT", "after": 21549990.0},
            "next": {"index": 117, "reason": "store:purchase",
                     "domain_hint": "CREDITS_HINT", "before": 21992723.9},
            "delta_to_explain": 442733.9,
            "source_evidence_required": True,
        }],
        "findings_truncated": True,
        "blockers": ["ACCOUNT_LEDGER_SEQUENCE_DISCONTINUITY"],
    }
    with patch("state_manager.load_db", return_value={"ledger": []}), patch(
        "core.account_ledger_audit.audit_account_ledger", return_value=result
    ) as audit, patch(
        "handlers.system_checks_handler.check_exchange",
        return_value={"public_gate": "CLOSED", "public_ready": False, "verdict": "BLOCKED",
                      "detail": "account_ledger=BLOCKED(ACCOUNT_LEDGER_SEQUENCE_DISCONTINUITY)"},
    ):
        bot.handlers["check_owner_ledger"](_message())

    audit.assert_called_once()
    output = bot.replies[-1]
    assert "OWNER ACCOUNT LEDGER — READ ONLY" in output
    assert "Credits continuity breaks: 12" in output
    assert "Row arithmetic errors: 0" in output
    assert "POSSIBLE_MIXED_DOMAIN_BOUNDARY" in output
    assert "source evidence required" in output
    assert "No DB, ledger, Credits, wallets, or gates changed" in output


def test_non_owner_cannot_read_owner_ledger(monkeypatch):
    bot = _register(monkeypatch)
    with patch("core.account_ledger_audit.audit_account_ledger") as audit:
        bot.handlers["check_owner_ledger"](_message(uid="5010371391"))
    audit.assert_not_called()
    assert "OWNER ONLY" in bot.replies[-1]


def test_owner_ledger_command_rejects_non_private_chat(monkeypatch):
    bot = _register(monkeypatch)
    with patch("core.account_ledger_audit.audit_account_ledger") as audit:
        bot.handlers["check_owner_ledger"](_message(chat_type="group"))
    audit.assert_not_called()
    assert "שיחה פרטית" in bot.replies[-1]



def test_reconciled_alpha_consolidation_is_not_labeled_unresolved(monkeypatch):
    bot = _register(monkeypatch)
    result = {
        "scope": "read_only",
        "status": "BLOCKED",
        "rows_checked": 144,
        "continuity_break_count": 2,
        "arithmetic_error_count": 0,
        "malformed_global_rows": 0,
        "current_wallet_credits": 10.072775,
        "ledger_tail_after": 10.072775,
        "current_balance_matches_tail": True,
        "findings": [{
            "type": "RECONCILED_ALPHA_CONSOLIDATION",
            "reconciled": True,
            "source_evidence_required": False,
            "previous": {
                "index": 1, "reason": "P0_AUTHORITY_VERIFY",
                "domain_hint": "UNKNOWN_HINT", "after": 1316.0,
            },
            "next": {
                "index": 3, "reason": "staking:stake",
                "domain_hint": "CREDITS_HINT", "before": 11815.0,
            },
            "delta_to_explain": 10499.0,
            "source_evidence": {
                "source_match_status": "VERIFIED_HISTORICAL_ALPHA_CONSOLIDATION",
                "resolves_gap": True,
                "alpha_consolidations": [{
                    "index": 2,
                    "resolves_gap": True,
                    "resolution_basis": "VERSION_CONTROLLED_SOURCE_AND_DESTINATION_STATE_MATCH",
                    "source_commit": "d013b914bbca1b6c2f50e768d461213ae1cbfbef",
                }],
            },
        }],
        "findings_truncated": False,
        "blockers": ["ACCOUNT_LEDGER_SEQUENCE_DISCONTINUITY"],
    }
    with patch("state_manager.load_db", return_value={"ledger": []}), patch(
        "core.account_ledger_audit.audit_account_ledger", return_value=result
    ), patch(
        "handlers.system_checks_handler.check_exchange",
        return_value={"public_gate": "CLOSED", "public_ready": False, "verdict": "BLOCKED",
                      "detail": "account_ledger=BLOCKED(ACCOUNT_LEDGER_SEQUENCE_DISCONTINUITY)"},
    ):
        bot.handlers["check_owner_ledger"](_message())

    output = bot.replies[-1]
    assert "source evidence verified" in output
    assert "source evidence required" not in output
    assert "resolves_gap=True" in output
    assert "VERSION_CONTROLLED_SOURCE_AND_DESTINATION_STATE_MATCH" in output



def test_owner_ledger_bundle_includes_staking_review_and_exchange_gate(monkeypatch):
    bot = _register(monkeypatch)
    uid = OWNER_UID
    stake_time = "2026-09-02T15:18:54.485431+00:00"
    unstake_time = "2026-09-02T15:19:42.806812+00:00"
    from datetime import datetime
    created_at = datetime.fromisoformat(stake_time).timestamp()
    db = {
        "users": {uid: {"wallet": {"credits": 110.0, "staked": 100.0}}},
        "stake_positions": {
            "sp_test_legacy": {
                "id": "sp_test_legacy", "uid": uid, "amount": 100.0,
                "status": "locked", "created_at": created_at, "unlocks_at": 0,
            },
        },
        "ledger": [
            {
                "time": stake_time, "uid": uid, "before": 500.0, "amount": -100.0,
                "after": 400.0, "reason": "staking:stake",
                "meta": {"command": "stake", "staked_before": 0.0, "staked_after": 100.0},
            },
            {
                "time": unstake_time, "uid": uid, "before": 400.0, "amount": 100.0,
                "after": 500.0, "reason": "staking:unstake",
                "meta": {"command": "unstake", "staked_before": 100.0, "staked_after": 0.0},
            },
        ],
    }
    before = __import__("copy").deepcopy(db)
    fake_audit = {
        "scope": "read_only", "status": "BLOCKED", "rows_checked": 2,
        "credits_sequence_rows_checked": 2, "non_credits_rows_skipped": 0,
        "continuity_break_count": 1, "observed_discontinuity_count": 1,
        "resolved_gap_count": 0, "unresolved_continuity_break_count": 1,
        "arithmetic_error_count": 0, "malformed_global_rows": 0,
        "current_wallet_credits": 110.0, "ledger_tail_after": 500.0,
        "current_balance_matches_tail": False,
        "findings": [{
            "type": "SEQUENCE_GAP_REQUIRES_SOURCE_EVIDENCE",
            "previous": {"index": 0, "reason": "staking:stake", "domain_hint": "CREDITS_HINT", "after": 400.0},
            "next": {"index": 1, "reason": "staking:unstake", "domain_hint": "CREDITS_HINT", "before": 400.0},
            "delta_to_explain": 0.0, "source_evidence_required": True,
            "source_evidence": {"source_match_status": "NO_DIRECT_SOURCE_MATCH", "resolves_gap": False},
        }],
        "blockers": ["ACCOUNT_LEDGER_SEQUENCE_DISCONTINUITY"],
        "findings_truncated": False,
    }
    with patch("state_manager.load_db", return_value=db), patch(
        "core.account_ledger_audit.audit_account_ledger", return_value=fake_audit
    ), patch(
        "handlers.system_checks_handler.check_exchange",
        return_value={"public_gate": "CLOSED", "public_ready": False, "verdict": "BLOCKED",
                      "detail": "account_ledger=BLOCKED(ACCOUNT_LEDGER_SEQUENCE_DISCONTINUITY)"},
    ):
        bot.handlers["check_owner_ledger"](_message())

    output = bot.replies[-1]
    assert "OWNER ACCOUNT LEDGER — READ ONLY" in output
    assert "FORENSIC BUNDLE: ledger + staking guard + exchange" in output
    assert "LEGACY_UNSTAKE_AMBIGUITY" in output
    assert "sp_test_legacy" in output
    assert "Public trading gate: CLOSED" in output
    assert "Exchange verdict: BLOCKED" in output
    assert db == before



def test_ledger_evidence_command_is_private_owner_only_and_redacts_other_accounts(monkeypatch):
    bot = _register(monkeypatch)
    ledger = [{} for _ in range(206)]
    ledger[65] = {
        "time": "2026-09-09T17:35:55.403916+00:00", "uid": OWNER_UID,
        "before": 0.0, "amount": 50.0, "after": 50.0,
        "reason": "admin:test_grant", "meta": {"source": "giveme", "command": "giveme"},
    }
    ledger[199] = {
        "time": "2026-10-05T14:57:50+00:00", "uid": OWNER_UID,
        "before": 2.191775, "amount": -1.0, "after": 1.191775,
        "reason": "p2p:transfer_sent",
        "meta": {"transfer_id": "TRANSFER-owner-test", "recipient_uid": "PRIVATE_OTHER_UID"},
    }
    ledger[200] = {
        "time": "2026-10-05T14:57:50+00:00", "uid": "PRIVATE_OTHER_UID",
        "before": 999.0, "amount": 888.0, "after": 111.0,
        "reason": "private:other_account", "meta": {"purchase_id": "SECRET_PURCHASE"},
    }
    ledger[202] = {
        "time": "2026-10-05T16:19:45+00:00", "uid": OWNER_UID,
        "before": 6.191775, "amount": 0.9, "after": 7.091775,
        "reason": "store:p2p_sale",
        "meta": {"purchase_id": "purchase:owner:test", "item_id": "market_smoke"},
    }
    db = {
        "ledger": ledger,
        "purchases": {
            "purchase:owner:test": {
                "status": "FULFILLED", "item_id": "market_smoke", "price": 1.0,
                "seller_payout": 0.9, "commission": 0.1,
                "created_at": "2026-10-05T16:19:45+00:00", "buyer_uid": "PRIVATE_OTHER_UID",
            },
        },
        "processed_transfers": {"processed:owner:test": "TRANSFER-owner-test"},
    }
    before = __import__("copy").deepcopy(db)
    with patch("state_manager.load_db", return_value=db):
        bot.handlers["check_ledger_evidence"](_message("/check_ledger_evidence"))
    output = bot.replies[-1]
    assert "OWNER LEDGER SOURCE EVIDENCE — READ ONLY" in output
    assert "source=giveme" in output
    assert "TRANSFER-owner-test" in output
    assert "seller_payout=0.9" in output
    assert "other-account row; details withheld" in output
    assert "PRIVATE_OTHER_UID" not in output
    assert "SECRET_PURCHASE" not in output
    assert "999.0" not in output
    assert "No changes" in output
    assert db == before


def test_ledger_evidence_command_rejects_non_owner_and_non_private_chat(monkeypatch):
    bot = _register(monkeypatch)
    with patch("state_manager.load_db") as load_db:
        bot.handlers["check_ledger_evidence"](_message("/check_ledger_evidence", uid="5010371391"))
        bot.handlers["check_ledger_evidence"](_message("/check_ledger_evidence", chat_type="group"))
    load_db.assert_not_called()
    assert "שיחה פרטית" in bot.replies[-1]
