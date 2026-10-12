from copy import deepcopy
from datetime import datetime, timezone
from unittest.mock import patch

import core.bnb_treasury_reconcile as reconcile


OWNER_UID = "8789977826"
OWNER_WALLET = "0x468328B2a7C9b5629e87844Bb4531e7409400b34"
CANONICAL_TREASURY = "0x1111111111111111111111111111111111111111"  # safe, non-quarantined test fixture only
NOW = datetime(2026, 10, 12, 12, 0, tzinfo=timezone.utc)


def _db(treasury=OWNER_WALLET):
    return {
        "bsc_settings": {
            "network": "bsc",
            "rpc": "https://bsc-dataseed.binance.org/",
            "chain_id": 56,
            "treasury_wallet": treasury,
            "confirmations": 15,
        },
        "wallet_bindings": {
            OWNER_UID: {
                "uid": OWNER_UID,
                "chain": "bsc",
                "address": OWNER_WALLET,
                "verified": True,
            }
        },
        "users": {OWNER_UID: {"wallet": {"credits": 8.091775, "token_balance": 999.0}}},
        "ledger": [{"reason": "historic", "amount": 1.0}],
        "slh_token_ledger": [{"reason": "historic", "amount": 1.0}],
        "bnb_treasury_reconcile_pending": {},
        "bnb_treasury_reconcile_audit": [],
    }


def _bind_state(monkeypatch, db):
    monkeypatch.setattr(reconcile.state_manager, "load_db", lambda: db)
    monkeypatch.setattr(reconcile.state_manager, "atomic_update", lambda mutate: mutate(db))


def _env(monkeypatch, treasury=CANONICAL_TREASURY, gate="0"):
    monkeypatch.setenv("SLH_BSC_CANONICAL_TREASURY", treasury)
    monkeypatch.setenv("BNB_DEPOSITS_OPEN", gate)


def test_prepare_previews_canonical_target_without_changing_treasury_or_financial_ledgers(monkeypatch):
    db = _db()
    before = deepcopy(db)
    _bind_state(monkeypatch, db)
    _env(monkeypatch)
    monkeypatch.setattr(reconcile, "is_owner", lambda uid: str(uid) == OWNER_UID)

    result = reconcile.prepare_bnb_treasury_reconcile(OWNER_UID, now=NOW)

    assert result["status"] == "PREPARED"
    assert result["previous_treasury"].lower() == OWNER_WALLET.lower()
    assert result["canonical_treasury"].lower() == CANONICAL_TREASURY.lower()
    assert db["bsc_settings"]["treasury_wallet"] == before["bsc_settings"]["treasury_wallet"]
    assert db["ledger"] == before["ledger"]
    assert db["slh_token_ledger"] == before["slh_token_ledger"]
    assert db["users"] == before["users"]
    assert result["expires_at"]


def test_confirm_updates_only_treasury_setting_and_records_audit_without_opening_gate(monkeypatch):
    db = _db()
    _bind_state(monkeypatch, db)
    _env(monkeypatch)
    monkeypatch.setattr(reconcile, "is_owner", lambda uid: str(uid) == OWNER_UID)

    preview = reconcile.prepare_bnb_treasury_reconcile(OWNER_UID, now=NOW)
    result = reconcile.confirm_bnb_treasury_reconcile(
        OWNER_UID, preview["confirmation_id"], now=NOW
    )

    assert result["status"] == "RECONCILED"
    assert result["treasury_wallet"].lower() == CANONICAL_TREASURY.lower()
    assert db["bsc_settings"]["treasury_wallet"].lower() == CANONICAL_TREASURY.lower()
    assert db["ledger"] == [{"reason": "historic", "amount": 1.0}]
    assert db["slh_token_ledger"] == [{"reason": "historic", "amount": 1.0}]
    assert db["users"][OWNER_UID]["wallet"]["credits"] == 8.091775
    assert db["bnb_treasury_reconcile_audit"][-1]["status"] == "RECONCILED"
    assert db["bnb_treasury_reconcile_audit"][-1]["actor_uid"] == OWNER_UID
    assert not db["bnb_treasury_reconcile_pending"]
    assert __import__("os").environ["BNB_DEPOSITS_OPEN"] == "0"
    assert result["public_bnb_gate"] == "CLOSED"


def test_non_owner_cannot_preview_or_confirm(monkeypatch):
    db = _db()
    _bind_state(monkeypatch, db)
    _env(monkeypatch)
    monkeypatch.setattr(reconcile, "is_owner", lambda _uid: False)

    preview = reconcile.prepare_bnb_treasury_reconcile("5010371391", now=NOW)
    confirm = reconcile.confirm_bnb_treasury_reconcile("5010371391", "anything", now=NOW)

    assert preview["status"] == "FORBIDDEN"
    assert confirm["status"] == "FORBIDDEN"
    assert db["bsc_settings"]["treasury_wallet"].lower() == OWNER_WALLET.lower()


def test_canonical_treasury_must_not_alias_any_verified_depositor(monkeypatch):
    db = _db()
    _bind_state(monkeypatch, db)
    _env(monkeypatch, treasury=OWNER_WALLET)
    monkeypatch.setattr(reconcile, "is_owner", lambda _uid: True)

    result = reconcile.prepare_bnb_treasury_reconcile(OWNER_UID, now=NOW)

    assert result["status"] == "BLOCKED"
    assert result["code"] == "BNB_TREASURY_MATCHES_BOUND_WALLET"
    assert db["bsc_settings"]["treasury_wallet"].lower() == OWNER_WALLET.lower()


def test_treasury_reconcile_is_blocked_unless_public_gate_flag_is_explicitly_closed(monkeypatch):
    db = _db()
    _bind_state(monkeypatch, db)
    _env(monkeypatch, gate="1")
    monkeypatch.setattr(reconcile, "is_owner", lambda _uid: True)

    result = reconcile.prepare_bnb_treasury_reconcile(OWNER_UID, now=NOW)

    assert result["status"] == "BLOCKED"
    assert result["code"] == "BNB_DEPOSITS_OPEN_FLAG_NOT_ZERO"
    assert db["bsc_settings"]["treasury_wallet"].lower() == OWNER_WALLET.lower()


def test_confirmation_is_rejected_if_treasury_changes_after_preview(monkeypatch):
    db = _db()
    _bind_state(monkeypatch, db)
    _env(monkeypatch)
    monkeypatch.setattr(reconcile, "is_owner", lambda _uid: True)

    preview = reconcile.prepare_bnb_treasury_reconcile(OWNER_UID, now=NOW)
    db["bsc_settings"]["treasury_wallet"] = "0x1111111111111111111111111111111111111111"
    result = reconcile.confirm_bnb_treasury_reconcile(
        OWNER_UID, preview["confirmation_id"], now=NOW
    )

    assert result["status"] == "BLOCKED"
    assert result["code"] == "BNB_TREASURY_CHANGED_AFTER_PREVIEW"
    assert db["bsc_settings"]["treasury_wallet"].lower() == "0x1111111111111111111111111111111111111111"


def test_confirmation_is_rejected_if_canonical_environment_target_changes(monkeypatch):
    db = _db()
    _bind_state(monkeypatch, db)
    _env(monkeypatch)
    monkeypatch.setattr(reconcile, "is_owner", lambda _uid: True)

    preview = reconcile.prepare_bnb_treasury_reconcile(OWNER_UID, now=NOW)
    monkeypatch.setenv("SLH_BSC_CANONICAL_TREASURY", "0x2222222222222222222222222222222222222222")
    result = reconcile.confirm_bnb_treasury_reconcile(
        OWNER_UID, preview["confirmation_id"], now=NOW
    )

    assert result["status"] == "BLOCKED"
    assert result["code"] == "BNB_CANONICAL_TREASURY_CHANGED_AFTER_PREVIEW"
    assert db["bsc_settings"]["treasury_wallet"].lower() == OWNER_WALLET.lower()


def test_expired_preview_cannot_change_treasury(monkeypatch):
    db = _db()
    _bind_state(monkeypatch, db)
    _env(monkeypatch)
    monkeypatch.setattr(reconcile, "is_owner", lambda _uid: True)

    preview = reconcile.prepare_bnb_treasury_reconcile(OWNER_UID, now=NOW)
    later = NOW.replace(minute=6)
    result = reconcile.confirm_bnb_treasury_reconcile(
        OWNER_UID, preview["confirmation_id"], now=later
    )

    assert result["status"] == "EXPIRED"
    assert db["bsc_settings"]["treasury_wallet"].lower() == OWNER_WALLET.lower()


def test_known_quarantined_zuz_treasury_is_never_previewed_or_applied(monkeypatch):
    db = _db()
    before = deepcopy(db)
    _bind_state(monkeypatch, db)
    _env(monkeypatch, treasury="0x693db6c817083818696a7228aebfbd0cd3371f02")
    monkeypatch.setattr(reconcile, "is_owner", lambda _uid: True)

    preview = reconcile.prepare_bnb_treasury_reconcile(OWNER_UID, now=NOW)
    status = reconcile.inspect_bnb_treasury_reconcile(OWNER_UID)

    assert preview["status"] == "BLOCKED"
    assert preview["code"] == "BNB_CANONICAL_TREASURY_QUARANTINED_ZUZ"
    assert status["status"] == "BLOCKED"
    assert status["code"] == "BNB_CANONICAL_TREASURY_QUARANTINED_ZUZ"
    assert db["bsc_settings"]["treasury_wallet"] == before["bsc_settings"]["treasury_wallet"]
    assert db["ledger"] == before["ledger"]
    assert db["slh_token_ledger"] == before["slh_token_ledger"]
