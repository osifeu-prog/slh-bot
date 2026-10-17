from datetime import datetime, timedelta, timezone
import hashlib
from types import SimpleNamespace
from unittest.mock import Mock

import handlers.broadcast_handler as target
import core.system_checks as system_checks
import handlers.exchange_handler as exchange_handler
import core.slh_exchange_reconciliation as reserve_reconciliation


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


def _live_proof(ready=True):
    return {
        "status": "PASS" if ready else "BLOCKED",
        "checked_at": NOW.isoformat(),
        "railway_configured": "1",
        "public_gate": "OPEN" if ready else "CLOSED",
        "public_verdict": "OPEN" if ready else "BLOCKED",
        "public_readiness": bool(ready),
        "public_updated_at": 1791830000.0,
        "detail": "canonical public runtime proof passed" if ready else "live runtime proof blocked",
    }


def _install_db(monkeypatch, db):
    monkeypatch.setattr(target.state_manager, "load_db", lambda: db)

    def atomic_update(mutator):
        return mutator(db)

    monkeypatch.setattr(target.state_manager, "atomic_update", atomic_update)
    monkeypatch.setattr(
        exchange_handler,
        "require_fresh_live_exchange_proof",
        lambda: _live_proof(True),
    )
    monkeypatch.setattr(
        reserve_reconciliation,
        "audit_db",
        lambda _db: {
            "status": "PASS",
            "operational_status": "PASS",
            "read_only": True,
            "checked_cancelled_sell_orders": 3,
            "finding_count": 0,
            "findings": [],
            "blocking_finding_count": 0,
            "blocking_findings": [],
            "historical_finding_count": 0,
            "historical_findings": [],
        },
    )


def _install_send(monkeypatch):
    sent = []

    def send_one(bot, uid, text, next_allowed_at, *, reply_markup=None):
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




def test_voice_prepare_accepts_clear_broadcast_paraphrase_as_preview_only(monkeypatch):
    db = _db()
    _install_db(monkeypatch, db)
    bot = Mock()
    message = SimpleNamespace(
        from_user=SimpleNamespace(id=int(OWNER)),
        chat=SimpleNamespace(type="private", id=int(OWNER)),
    )

    # Voice transcription may add words while retaining an explicit prepare intent.
    answer = target.route_exchange_broadcast_voice(
        bot, message, "תכין לי הודעה לברודקאסט על המסחר הפנימי", now=NOW
    )

    assert answer is not None
    assert target.EXCHANGE_BROADCAST_TEXT in answer
    assert "תצוגה מקדימה בלבד" in answer
    assert db["exchange_broadcast_pending"][OWNER]["status"] == "PENDING_CONFIRMATION"
    bot.send_message.assert_not_called()


def test_voice_prepare_does_not_accept_negative_instruction(monkeypatch):
    db = _db()
    _install_db(monkeypatch, db)
    bot = Mock()
    message = SimpleNamespace(
        from_user=SimpleNamespace(id=int(OWNER)),
        chat=SimpleNamespace(type="private", id=int(OWNER)),
    )

    answer = target.route_exchange_broadcast_voice(
        bot, message, "אל תכין ברודקאסט למסחר פנימי", now=NOW
    )

    assert answer is not None
    assert "READ ONLY" in answer
    assert "exchange_broadcast_pending" not in db
    bot.send_message.assert_not_called()


def test_near_miss_voice_confirmation_gives_exact_retry_and_never_sends(monkeypatch):
    db = _db()
    _install_db(monkeypatch, db)
    target.prepare_exchange_broadcast(OWNER, now=NOW)
    sent = _install_send(monkeypatch)
    bot = Mock()
    message = SimpleNamespace(
        from_user=SimpleNamespace(id=int(OWNER)),
        chat=SimpleNamespace(type="private", id=int(OWNER)),
    )

    answer = target.route_exchange_broadcast_voice(
        bot,
        message,
        "אשר ושלח ברודקאסט למסחר הפנימי בבקשה עכשיו",
        now=NOW + timedelta(seconds=5),
    )

    assert answer is not None
    assert "לא נשלח" in answer
    assert "אשר ושלח ברודקאסט למסחר פנימי" in answer
    assert db["exchange_broadcast_pending"][OWNER]["status"] == "PENDING_CONFIRMATION"
    assert sent == []
    bot.send_message.assert_not_called()



def test_confirm_blocks_when_fresh_live_runtime_proof_is_not_open(monkeypatch):
    db = _db()
    _install_db(monkeypatch, db)
    target.prepare_exchange_broadcast(OWNER, now=NOW)
    monkeypatch.setattr(
        system_checks,
        "check_exchange_for_execution",
        lambda current: _fresh_check(True),
    )
    monkeypatch.setattr(
        exchange_handler,
        "require_fresh_live_exchange_proof",
        lambda: _live_proof(False),
    )
    sent = _install_send(monkeypatch)

    result = target.send_confirmed_exchange_broadcast(
        Mock(), OWNER, now=NOW + timedelta(seconds=5)
    )

    assert result["status"] == "BLOCKED"
    assert result["sent"] == 0
    assert sent == []
    assert db["exchange_broadcast_pending"][OWNER]["status"] == "BLOCKED"


def test_confirm_stops_during_broadcast_when_fresh_live_runtime_proof_closes(monkeypatch):
    user_ids = ("8789977826",) + tuple(str(i) for i in range(100, 130))
    db = _db(user_ids)
    _install_db(monkeypatch, db)
    target.prepare_exchange_broadcast(OWNER, now=NOW)
    local_checks = iter([_fresh_check(True)] * 20)
    monkeypatch.setattr(
        system_checks,
        "check_exchange_for_execution",
        lambda current: next(local_checks),
    )
    live_proofs = iter([_live_proof(True), _live_proof(False)])
    calls = []

    def check_live_runtime():
        calls.append(True)
        return next(live_proofs)

    monkeypatch.setattr(
        exchange_handler,
        "require_fresh_live_exchange_proof",
        check_live_runtime,
    )
    sent = _install_send(monkeypatch)

    result = target.send_confirmed_exchange_broadcast(
        Mock(), OWNER, now=NOW + timedelta(seconds=5)
    )

    assert result["status"] == "STOPPED_GATE_CLOSED"
    assert result["sent"] == 25
    assert len(sent) == 25
    assert len(calls) == 2
    assert db["exchange_broadcast_pending"][OWNER]["status"] == "STOPPED_GATE_CLOSED"


def test_broadcast_blocks_before_any_recipient_when_reserve_audit_fails(monkeypatch):
    db = _db()
    _install_db(monkeypatch, db)
    target.prepare_exchange_broadcast(OWNER, now=NOW)
    monkeypatch.setattr(
        system_checks,
        "check_exchange_for_execution",
        lambda _db: _fresh_check(True),
    )
    monkeypatch.setattr(
        reserve_reconciliation,
        "audit_db",
        lambda _db: {
            "status": "FAIL",
            "read_only": True,
            "checked_cancelled_sell_orders": 7,
            "finding_count": 11,
            "findings": [{"code": "CANCELLED_SELL_ORDER_MISSING_NORMAL_RELEASE"}],
        },
    )
    sent = _install_send(monkeypatch)

    result = target.send_confirmed_exchange_broadcast(
        Mock(), OWNER, now=NOW + timedelta(seconds=5)
    )

    assert result["status"] == "BLOCKED"
    assert result["sent"] == 0
    assert sent == []
    assert db["exchange_broadcast_pending"][OWNER]["status"] == "BLOCKED"
    receipt = db["exchange_broadcast_audit"][-1]["fresh_exchange_check"]
    assert receipt["reserve_audit_check"] == "BLOCKED"
    assert receipt["reserve_audit_status"] == "FAIL"
    assert receipt["reserve_audit_finding_count"] == 11


def test_voice_exchange_reserve_audit_query_shows_all_findings_read_only(monkeypatch):
    db = _db()
    _install_db(monkeypatch, db)
    monkeypatch.setattr(target.state_manager, "atomic_update", lambda _mutator: (_ for _ in ()).throw(AssertionError("audit must be read-only")))
    report = {
        "status": "FAIL",
        "read_only": True,
        "checked_cancelled_sell_orders": 7,
        "finding_count": 2,
        "findings": [
            {
                "code": "CANCELLED_SELL_ORDER_MISSING_NORMAL_RELEASE",
                "ledger": "ledger",
                "order_id": "O0000000006",
                "uid_suffix": "7826",
                "reserve_delta": "-5.0",
                "normal_release_delta": "0",
                "correction_delta": 0,
            },
            {
                "code": "MANUAL_RESERVE_CORRECTION_REQUIRES_REVIEW",
                "ledger": "slh_token_ledger",
                "order_id": "O0000000009",
                "event_ids": ["correction:missed_release:O0000000009"],
                "correction_delta": "10000.0",
            },
        ],
    }
    monkeypatch.setattr(reserve_reconciliation, "audit_db", lambda current: report)
    message = SimpleNamespace(
        from_user=SimpleNamespace(id=int(OWNER)),
        chat=SimpleNamespace(type="private"),
    )
    bot = Mock()

    reply = target.route_exchange_broadcast_voice(
        bot,
        message,
        "בדוק את כל ממצאי רזרבות המסחר",
        now=NOW,
    )

    assert reply is not None
    messages = [call.args[1] for call in bot.send_message.call_args_list]
    delivered = "\n".join(messages)
    assert "Reserve audit: FAIL" in delivered
    assert "finding_count=2" in delivered
    assert "CANCELLED_SELL_ORDER_MISSING_NORMAL_RELEASE" in delivered
    assert "O0000000006" in delivered
    assert "uid…7826" in delivered
    assert "corr=0" in delivered
    assert "MANUAL_RESERVE_CORRECTION_REQUIRES_REVIEW" in delivered
    assert "correction:missed_release:O0000000009" in delivered
    assert "READ ONLY" in delivered
    assert "לא שונו פקודות" in reply
    assert bot.reply_to.call_count == 0


def test_voice_exchange_reserve_audit_query_rejects_non_owner_and_groups():
    bot = Mock()
    transcript = "בדוק את כל ממצאי רזרבות המסחר"

    non_owner = SimpleNamespace(
        from_user=SimpleNamespace(id=42),
        chat=SimpleNamespace(type="private"),
    )
    assert "OWNER" in target.route_exchange_broadcast_voice(bot, non_owner, transcript)

    group_owner = SimpleNamespace(
        from_user=SimpleNamespace(id=int(OWNER)),
        chat=SimpleNamespace(type="group"),
    )
    assert "פרטית" in target.route_exchange_broadcast_voice(bot, group_owner, transcript)
    bot.reply_to.assert_not_called()
