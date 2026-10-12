from types import SimpleNamespace
from unittest.mock import Mock

import handlers.bnb_empirical_handler as target


OWNER_UID = "8789977826"
TX_HASH = "0x" + "a" * 64


def _message(uid=OWNER_UID, chat_type="private"):
    return SimpleNamespace(
        from_user=SimpleNamespace(id=int(uid)),
        chat=SimpleNamespace(type=chat_type, id=int(uid) if uid.isdigit() else 123),
    )


def test_voice_bnb_existing_transfer_prepare_only_previews(monkeypatch):
    calls = []
    monkeypatch.setattr(
        target,
        "prepare_auto_existing_bnb_reconcile",
        lambda uid, *, now=None: calls.append((uid, now)) or {
            "status": "PREPARED",
            "tx_hash": TX_HASH,
            "amount_wei": 10**16,
            "amount_bnb": 0.01,
            "estimated_credits": 10,
            "confirmations": 20,
            "required_confirmations": 15,
        },
    )
    monkeypatch.setattr(target, "_auto_preview_reply", lambda result: "PREVIEW ONLY")
    bot = Mock()

    answer = target.route_bnb_existing_tx_voice(
        bot, _message(), "הכן בדיקת BNB מההעברה הקיימת"
    )

    assert calls == [(OWNER_UID, None)]
    assert "PREVIEW ONLY" in answer
    assert "אשר את העברת BNB הקיימת" in answer
    assert bot.send_message.call_count == 0


def test_voice_bnb_confirmation_requires_auto_preview_and_confirms_exact_pending_tx(monkeypatch):
    db = {
        "bnb_empirical_reconcile_pending": {
            OWNER_UID: {
                "status": "PENDING_CONFIRMATION",
                "confirmation_source": "auto_existing_0_01_canary",
                "tx_hash": TX_HASH,
                "amount_wei": 10**16,
            }
        }
    }
    calls = []
    monkeypatch.setattr(target.state_manager, "load_db", lambda: db)
    monkeypatch.setattr(
        target,
        "confirm_existing_bnb_reconcile",
        lambda uid, *, tx_hash=None, now=None: calls.append((uid, tx_hash, now))
        or {"status": "PASS", "tx_hash": tx_hash, "credits": 10, "gate_remained_closed": True},
    )
    monkeypatch.setattr(target, "_confirm_reply", lambda result: "SETTLEMENT PASS")

    answer = target.route_bnb_existing_tx_voice(
        Mock(), _message(), "אשר את העברת BNB הקיימת"
    )

    assert calls == [(OWNER_UID, TX_HASH, None)]
    assert answer == "SETTLEMENT PASS"


def test_voice_bnb_confirmation_rejects_manual_or_ambiguous_pending_preview(monkeypatch):
    db = {
        "bnb_empirical_reconcile_pending": {
            OWNER_UID: {
                "status": "PENDING_CONFIRMATION",
                "confirmation_source": "manual_tx_hash",
                "tx_hash": TX_HASH,
                "amount_wei": 10**18,
            }
        }
    }
    monkeypatch.setattr(target.state_manager, "load_db", lambda: db)
    monkeypatch.setattr(
        target,
        "confirm_existing_bnb_reconcile",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("must not confirm")),
    )

    answer = target.route_bnb_existing_tx_voice(
        Mock(), _message(), "אשר את העברת BNB הקיימת"
    )

    assert "תצוגה מקדימה אוטומטית" in answer
    assert "לא בוצע settlement" in answer


def test_voice_bnb_reconciliation_is_owner_private_only(monkeypatch):
    called = []
    monkeypatch.setattr(
        target,
        "prepare_auto_existing_bnb_reconcile",
        lambda uid, *, now=None: called.append(uid) or {"status": "NOT_FOUND"},
    )

    non_owner = target.route_bnb_existing_tx_voice(
        Mock(), _message(uid="12345"), "הכן בדיקת BNB מההעברה הקיימת"
    )
    group = target.route_bnb_existing_tx_voice(
        Mock(), _message(chat_type="group"), "הכן בדיקת BNB מההעברה הקיימת"
    )

    assert "OWNER" in non_owner
    assert "פרטית" in group
    assert called == []


def test_voice_bnb_reconciliation_ignores_unrelated_status_phrase():
    answer = target.route_bnb_existing_tx_voice(
        Mock(), _message(), "בדוק BNB"
    )
    assert answer is None


def test_prepare_existing_bnb_reconcile_persists_voice_confirmation_source(monkeypatch):
    db = {
        "settlement_evidence": {},
        "ledger": [],
        "bnb_empirical_reconcile_pending": {},
    }
    monkeypatch.setattr(
        target,
        "_inspect_existing_bnb_tx",
        lambda uid, tx_hash: {
            "status": "OK",
            "tx_hash": TX_HASH,
            "amount_wei": 10**16,
            "amount_bnb": 0.01,
            "estimated_credits": 10,
            "confirmations": 20,
            "required_confirmations": 15,
            "sender": "0x1111111111111111111111111111111111111111",
            "treasury": "0x2222222222222222222222222222222222222222",
        },
    )
    monkeypatch.setattr(target, "_current_pass_evidence", lambda *args, **kwargs: False)
    monkeypatch.setattr(target, "_matching_ledger_entries", lambda *args, **kwargs: [])
    monkeypatch.setattr(target.state_manager, "atomic_update", lambda mutate: mutate(db))

    result = target.prepare_existing_bnb_reconcile(
        OWNER_UID,
        TX_HASH,
        confirmation_source="auto_existing_0_01_canary",
    )

    assert result["status"] == "PREPARED"
    assert db["bnb_empirical_reconcile_pending"][OWNER_UID]["confirmation_source"] == "auto_existing_0_01_canary"
