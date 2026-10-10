from datetime import datetime, timedelta, timezone
import hashlib
from types import SimpleNamespace
from unittest.mock import Mock

import handlers.broadcast_handler as target
import core.system_checks as system_checks


OWNER = str(target.OWNER_TELEGRAM_ID)
NOW = datetime(2026, 10, 9, 9, 0, tzinfo=timezone.utc)


def _db(user_ids=("8789977826", "42", "43")):
    return {
        "users": {str(uid): {} for uid in user_ids},
        "exchange_orders": {},
        "exchange_trades": [],
        "exchange_requests": {},
    }


def _fresh_check(ready=True):
    return {
        "ok": ready,
        "execution_ready": ready,
        "public_gate": "OPEN" if ready else "CLOSED",
        "verdict": "OPEN" if ready else "BLOCKED",
        "public_ready": ready,
        "order_book_integrity": ready,
        "trade_integrity": ready,
        "money_invariants": ready,
        "open_orders": 0,
        "detail": "public state clean" if ready else "public exchange gate is CLOSED",
    }


def _install_db(monkeypatch, db):
    monkeypatch.setattr(target.state_manager, "load_db", lambda: db)

    def atomic_update(mutator):
        return mutator(db)

    monkeypatch.setattr(target.state_manager, "atomic_update", atomic_update)


def _install_send(monkeypatch):
    sent = []

    def send_one(bot, uid, text, next_allowed_at):
        bot.send_message(uid, text)
        sent.append((str(uid), text))
        return True, next_allowed_at

    monkeypatch.setattr(target, "_send_one", send_one)
    return sent


def test_voice_prepare_creates_preview_only_for_owner_private_chat(monkeypatch):
    db = _db()
    _install_db(monkeypatch, db)
    bot = Mock()
    message = SimpleNamespace(
        from_user=SimpleNamespace(id=int(OWNER)),
        chat=SimpleNamespace(type="private", id=int(OWNER)),
    )

    answer = target.route_exchange_broadcast_voice(
        bot, message, "הכן ברודקאסט למסחר פנימי", now=NOW
    )

    assert answer is not None
    assert target.EXCHANGE_BROADCAST_TEXT in answer
    assert "אשר ושלח ברודקאסט למסחר פנימי" in answer
    assert db["exchange_broadcast_pending"][OWNER]["status"] == "PENDING_CONFIRMATION"
    bot.send_message.assert_not_called()


def test_voice_prepare_rejects_non_owner_and_group_chat(monkeypatch):
    db = _db()
    _install_db(monkeypatch, db)
    bot = Mock()

    non_owner = SimpleNamespace(
        from_user=SimpleNamespace(id=42),
        chat=SimpleNamespace(type="private", id=42),
    )
    answer = target.route_exchange_broadcast_voice(
        bot, non_owner, "הכן ברודקאסט למסחר פנימי", now=NOW
    )
    assert "OWNER" in answer
    assert "exchange_broadcast_pending" not in db

    group_owner = SimpleNamespace(
        from_user=SimpleNamespace(id=int(OWNER)),
        chat=SimpleNamespace(type="group", id=-100123),
    )
    answer = target.route_exchange_broadcast_voice(
        bot, group_owner, "הכן ברודקאסט למסחר פנימי", now=NOW
    )
    assert "פרטי" in answer
    assert "exchange_broadcast_pending" not in db


def test_confirm_blocks_without_fresh_open_exchange_proof(monkeypatch):
    db = _db()
    _install_db(monkeypatch, db)
    target.prepare_exchange_broadcast(OWNER, now=NOW)
    monkeypatch.setattr(system_checks, "check_exchange_for_execution", lambda current: _fresh_check(False))
    sent = _install_send(monkeypatch)
    bot = Mock()

    result = target.send_confirmed_exchange_broadcast(bot, OWNER, now=NOW + timedelta(seconds=5))

    assert result["status"] == "BLOCKED"
    assert sent == []
    assert db["exchange_broadcast_pending"][OWNER]["status"] == "BLOCKED"


def test_confirm_uses_fresh_proof_sends_exact_message_and_cannot_replay(monkeypatch):
    db = _db()
    _install_db(monkeypatch, db)
    target.prepare_exchange_broadcast(OWNER, now=NOW)
    checks = []
    monkeypatch.setattr(
        system_checks,
        "check_exchange_for_execution",
        lambda current: checks.append(True) or _fresh_check(True),
    )
    sent = _install_send(monkeypatch)
    bot = Mock()

    result = target.send_confirmed_exchange_broadcast(bot, OWNER, now=NOW + timedelta(seconds=5))

    assert result["status"] == "SENT"
    assert result["sent"] == 3
    assert len(checks) >= 2  # atomic claim plus a separate pre-send check
    assert [message for _, message in sent] == [target.EXCHANGE_BROADCAST_TEXT] * 3
    assert db["exchange_broadcast_pending"][OWNER]["status"] == "SENT"

    replay = target.send_confirmed_exchange_broadcast(bot, OWNER, now=NOW + timedelta(seconds=8))
    assert replay["status"] in {"ALREADY_HANDLED", "NOT_PENDING"}
    assert len(sent) == 3


def test_confirm_stops_mid_broadcast_when_exchange_gate_closes(monkeypatch):
    user_ids = ("8789977826",) + tuple(str(i) for i in range(100, 130))
    db = _db(user_ids)
    _install_db(monkeypatch, db)
    target.prepare_exchange_broadcast(OWNER, now=NOW)
    checks = iter([_fresh_check(True), _fresh_check(True), _fresh_check(False)])
    monkeypatch.setattr(
        system_checks,
        "check_exchange_for_execution",
        lambda current: next(checks),
    )
    sent = _install_send(monkeypatch)
    bot = Mock()

    result = target.send_confirmed_exchange_broadcast(bot, OWNER, now=NOW + timedelta(seconds=5))

    assert result["status"] == "STOPPED_GATE_CLOSED"
    assert result["sent"] == 25
    assert result["target_count"] == 31
    assert len(sent) == 25
    assert db["exchange_broadcast_pending"][OWNER]["status"] == "STOPPED_GATE_CLOSED"


def test_expired_exchange_broadcast_confirmation_does_not_send(monkeypatch):
    db = _db()
    _install_db(monkeypatch, db)
    target.prepare_exchange_broadcast(OWNER, now=NOW)
    monkeypatch.setattr(system_checks, "check_exchange_for_execution", lambda current: _fresh_check(True))
    sent = _install_send(monkeypatch)
    bot = Mock()

    result = target.send_confirmed_exchange_broadcast(
        bot, OWNER, now=NOW + timedelta(minutes=6)
    )

    assert result["status"] == "EXPIRED"
    assert sent == []



def test_natural_language_exchange_broadcast_question_is_read_only(monkeypatch):
    db = _db()
    _install_db(monkeypatch, db)
    monkeypatch.setattr(
        system_checks,
        "check_exchange_for_execution",
        lambda current: _fresh_check(True),
    )
    bot = Mock()
    message = SimpleNamespace(
        from_user=SimpleNamespace(id=int(OWNER)),
        chat=SimpleNamespace(type="private", id=int(OWNER)),
    )

    answer = target.route_exchange_broadcast_voice(
        bot,
        message,
        "אפשר כבר לשלוח ברודקאסט למסחר פנימי?",
        now=NOW,
    )

    assert answer is not None
    assert "READ ONLY" in answer
    assert "OPEN" in answer
    assert "לא נשלחה הודעה" in answer
    assert "exchange_broadcast_pending" not in db
    bot.send_message.assert_not_called()



def test_voice_prepare_preview_reports_recipient_count_and_audience_fingerprint(monkeypatch):
    db = _db()
    _install_db(monkeypatch, db)
    bot = Mock()
    message = SimpleNamespace(
        from_user=SimpleNamespace(id=int(OWNER)),
        chat=SimpleNamespace(type="private", id=int(OWNER)),
    )

    answer = target.route_exchange_broadcast_voice(
        bot, message, "הכן ברודקאסט למסחר פנימי", now=NOW
    )

    record = db["exchange_broadcast_pending"][OWNER]
    expected_audience = sorted(str(uid) for uid in db["users"] if str(uid).isdigit() and int(uid) > 0)
    expected_hash = hashlib.sha256("|".join(expected_audience).encode("utf-8")).hexdigest()
    assert "3 משתמשים" in answer
    assert record["target_count"] == 3
    assert record["audience_sha256"] == expected_hash
    bot.send_message.assert_not_called()


def test_confirm_blocks_when_recipient_set_changes_after_preview(monkeypatch):
    db = _db()
    _install_db(monkeypatch, db)
    target.prepare_exchange_broadcast(OWNER, now=NOW)
    # A new Telegram user appears after the preview but before confirmation.
    db["users"]["44"] = {}
    monkeypatch.setattr(system_checks, "check_exchange_for_execution", lambda current: _fresh_check(True))
    sent = _install_send(monkeypatch)
    bot = Mock()

    result = target.send_confirmed_exchange_broadcast(
        bot, OWNER, now=NOW + timedelta(seconds=5)
    )

    assert result["status"] == "RECIPIENTS_CHANGED"
    assert result["sent"] == 0
    assert sent == []
    assert db["exchange_broadcast_pending"][OWNER]["status"] == "RECIPIENTS_CHANGED"

def test_voice_prepare_accepts_common_stt_polite_variant(monkeypatch):
    db = _db()
    _install_db(monkeypatch, db)
    bot = Mock()
    message = SimpleNamespace(
        from_user=SimpleNamespace(id=int(OWNER)),
        chat=SimpleNamespace(type="private", id=int(OWNER)),
    )

    answer = target.route_exchange_broadcast_voice(
        bot, message, "תכין לי הודעת ברודקאסט למסחר הפנימי", now=NOW
    )

    assert answer is not None
    assert "תצוגה מקדימה בלבד" in answer
    assert db["exchange_broadcast_pending"][OWNER]["status"] == "PENDING_CONFIRMATION"
    bot.send_message.assert_not_called()


def test_voice_confirm_accepts_common_explicit_stt_variant(monkeypatch):
    db = _db()
    _install_db(monkeypatch, db)
    target.prepare_exchange_broadcast(OWNER, now=NOW)
    monkeypatch.setattr(
        system_checks,
        "check_exchange_for_execution",
        lambda current: _fresh_check(True),
    )
    sent = _install_send(monkeypatch)
    bot = Mock()
    message = SimpleNamespace(
        from_user=SimpleNamespace(id=int(OWNER)),
        chat=SimpleNamespace(type="private", id=int(OWNER)),
    )

    answer = target.route_exchange_broadcast_voice(
        bot, message, "מאשר לשלוח את הברודקאסט למסחר הפנימי", now=NOW + timedelta(seconds=5)
    )

    assert answer is not None
    assert "נשלח" in answer
    assert db["exchange_broadcast_pending"][OWNER]["status"] == "SENT"
    assert sent
    assert all(text == target.EXCHANGE_BROADCAST_TEXT for _, text in sent)

