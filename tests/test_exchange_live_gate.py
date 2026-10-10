"""Regression coverage for send-time Exchange checks and the gated voice broadcast."""

from copy import deepcopy
from types import SimpleNamespace

import webapp
import handlers.exchange_handler as exchange_handler
import handlers.broadcast_handler as broadcast_handler


def _exchange_db(*, credits=10.0):
    return {
        "users": {
            "buyer": {
                "wallet": {
                    "credits": credits,
                    "token_balance": 0.0,
                    "live_token_balance": 0.0,
                    "exchange_reserved_slh": 0.0,
                    "exchange_reserved_credits": 0.0,
                }
            }
        },
        "exchange_orders": {},
        "exchange_trades": [],
        "exchange_requests": {},
        "exchange_sequence": 0,
        "ledger": [],
    }


def _green_exchange_check():
    return {
        "ok": True,
        "detail": "public state clean",
        "open_orders": 0,
        "public_gate": "OPEN",
        "public_ready": True,
        "verdict": "OPEN",
        "execution_ready": True,
        "order_book_integrity": True,
        "trade_integrity": True,
        "money_invariants": True,
    }


def test_rest_buy_checks_the_same_atomic_db_snapshot_and_returns_receipt(monkeypatch):
    db = _exchange_db()
    checked_snapshots = []

    monkeypatch.setattr(webapp, "authenticated_uid", lambda: "buyer")
    monkeypatch.setattr(webapp.state_manager, "atomic_update", lambda mutate: mutate(db))
    monkeypatch.setattr(exchange_handler, "require_public_open", lambda: None)

    def check(snapshot):
        checked_snapshots.append(snapshot)
        return _green_exchange_check()

    monkeypatch.setattr("core.system_checks.check_exchange_for_execution", check)

    response = webapp.app.test_client().post(
        "/api/v1/exchange/order",
        json={
            "side": "buy",
            "amount": "2",
            "price": "1",
            "client_request_id": "fresh-check-success",
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert len(checked_snapshots) == 1
    assert checked_snapshots[0] is db
    assert payload["execution_check"]["status"] == "PASS"
    assert payload["execution_check"]["execution_ready"] is True
    assert payload["execution_check"]["public_gate"] == "OPEN"
    assert payload["execution_check"]["checked_at"]
    assert payload["order_id"] in db["exchange_orders"]
    assert db["users"]["buyer"]["wallet"]["credits"] == 8.0
    assert db["exchange_orders"][payload["order_id"]]["status"] == "open"


def test_rest_buy_fails_closed_before_any_order_or_balance_mutation(monkeypatch):
    db = _exchange_db()
    before = deepcopy(db)
    blocked_check = {
        **_green_exchange_check(),
        "ok": False,
        "detail": "public exchange gate is CLOSED",
        "public_gate": "CLOSED",
        "public_ready": False,
        "verdict": "BLOCKED",
        "execution_ready": False,
        "order_book_integrity": False,
    }

    monkeypatch.setattr(webapp, "authenticated_uid", lambda: "buyer")
    monkeypatch.setattr(webapp.state_manager, "atomic_update", lambda mutate: mutate(db))
    monkeypatch.setattr(exchange_handler, "require_public_open", lambda: None)
    monkeypatch.setattr("core.system_checks.check_exchange_for_execution", lambda snapshot: blocked_check)

    response = webapp.app.test_client().post(
        "/api/v1/exchange/order",
        json={
            "side": "buy",
            "amount": "2",
            "price": "1",
            "client_request_id": "fresh-check-blocked",
        },
    )

    assert response.status_code == 409
    payload = response.get_json()
    assert payload["code"] == "EXCHANGE_FRESH_CHECK_BLOCKED"
    assert payload["exchange_check"]["public_gate"] == "CLOSED"
    assert db["exchange_orders"] == before["exchange_orders"]
    assert db["exchange_trades"] == before["exchange_trades"]
    assert db["users"]["buyer"]["wallet"]["credits"] == before["users"]["buyer"]["wallet"]["credits"]
    assert db["users"]["buyer"]["wallet"]["exchange_reserved_credits"] == 0.0


def _voice_message(uid, chat_type="private"):
    return SimpleNamespace(
        from_user=SimpleNamespace(id=uid),
        chat=SimpleNamespace(type=chat_type),
    )


def _broadcast_db():
    return {
        "users": {"101": {}, "202": {}},
        "exchange_broadcast_pending": {},
        "exchange_broadcast_audit": [],
    }


def test_voice_prepare_is_preview_only_owner_private_and_does_not_send(monkeypatch):
    owner = str(broadcast_handler.OWNER_TELEGRAM_ID)
    db = _broadcast_db()

    monkeypatch.setattr(broadcast_handler.state_manager, "atomic_update", lambda mutate: mutate(db))
    monkeypatch.setattr(broadcast_handler.state_manager, "load_db", lambda: db)

    answer = broadcast_handler.route_exchange_broadcast_voice(
        object(),
        _voice_message(int(owner)),
        "הכן ברודקאסט למסחר פנימי",
        now="2026-10-10T00:00:00Z",
    )

    assert "תצוגה מקדימה בלבד" in answer
    assert "לא נשלחה הודעה לאף משתמש" in answer
    assert "אינו DEX חיצוני ואינו IDO / Presale" in answer
    assert db["exchange_broadcast_pending"][owner]["status"] == "PENDING_CONFIRMATION"
    assert db["exchange_broadcast_audit"] == []

    denied = broadcast_handler.route_exchange_broadcast_voice(
        object(),
        _voice_message(int(owner), chat_type="group"),
        "אשר ושלח ברודקאסט למסחר פנימי",
        now="2026-10-10T00:00:01Z",
    )
    assert "פרטית" in denied
    assert db["exchange_broadcast_pending"][owner]["status"] == "PENDING_CONFIRMATION"


def test_voice_confirm_fails_closed_and_sends_nobody_when_exchange_is_closed(monkeypatch):
    owner = str(broadcast_handler.OWNER_TELEGRAM_ID)
    now = "2026-10-10T00:00:00Z"
    db = _broadcast_db()

    monkeypatch.setattr(broadcast_handler.state_manager, "atomic_update", lambda mutate: mutate(db))
    monkeypatch.setattr(broadcast_handler.state_manager, "load_db", lambda: db)
    monkeypatch.setattr(
        broadcast_handler,
        "_fresh_exchange_check",
        lambda snapshot: {
            **_green_exchange_check(),
            "ok": False,
            "detail": "public exchange gate is CLOSED",
            "public_gate": "CLOSED",
            "public_ready": False,
            "verdict": "BLOCKED",
            "execution_ready": False,
        },
    )

    prepared = broadcast_handler.prepare_exchange_broadcast(owner, now=now)
    assert prepared["status"] == "PREPARED"

    sent = []
    monkeypatch.setattr(
        broadcast_handler,
        "_send_one",
        lambda bot, uid, message, next_allowed: sent.append((uid, message)) or (True, next_allowed),
    )

    result = broadcast_handler.send_confirmed_exchange_broadcast(object(), owner, now=now)

    assert result["status"] == "BLOCKED"
    assert result["sent"] == 0
    assert sent == []
    assert db["exchange_broadcast_pending"][owner]["status"] == "BLOCKED"
    assert db["exchange_broadcast_audit"][-1]["status"] == "BLOCKED"


def test_voice_confirm_rechecks_fresh_exchange_and_sends_fixed_notice(monkeypatch):
    owner = str(broadcast_handler.OWNER_TELEGRAM_ID)
    now = "2026-10-10T00:00:00Z"
    db = _broadcast_db()
    checks = []

    monkeypatch.setattr(broadcast_handler.state_manager, "atomic_update", lambda mutate: mutate(db))
    monkeypatch.setattr(broadcast_handler.state_manager, "load_db", lambda: db)
    monkeypatch.setattr(broadcast_handler.time, "monotonic", lambda: 0.0)

    def green(snapshot):
        checks.append(snapshot)
        return _green_exchange_check()

    monkeypatch.setattr(broadcast_handler, "_fresh_exchange_check", green)

    prepared = broadcast_handler.prepare_exchange_broadcast(owner, now=now)
    assert prepared["status"] == "PREPARED"

    sent = []

    def send_one(bot, uid, message, next_allowed):
        sent.append((uid, message))
        return True, next_allowed

    monkeypatch.setattr(broadcast_handler, "_send_one", send_one)

    result = broadcast_handler.send_confirmed_exchange_broadcast(object(), owner, now=now)

    assert result["status"] == "SENT"
    assert result["target_count"] == 2
    assert result["sent"] == 2
    assert result["failed"] == 0
    assert len(checks) >= 2  # atomic claim check + fresh pre-send check
    assert {uid for uid, _ in sent} == {"101", "202"}
    assert all(message == broadcast_handler.EXCHANGE_BROADCAST_TEXT for _, message in sent)
    assert db["exchange_broadcast_pending"][owner]["status"] == "SENT"
    assert db["exchange_broadcast_audit"][-1]["fresh_exchange_check"]["public_gate"] == "OPEN"


def test_voice_broadcast_draft_expires_without_sending(monkeypatch):
    owner = str(broadcast_handler.OWNER_TELEGRAM_ID)
    db = _broadcast_db()
    monkeypatch.setattr(broadcast_handler.state_manager, "atomic_update", lambda mutate: mutate(db))

    prepared = broadcast_handler.prepare_exchange_broadcast(owner, now="2026-10-10T00:00:00Z")
    assert prepared["status"] == "PREPARED"

    sent = []
    monkeypatch.setattr(
        broadcast_handler,
        "_send_one",
        lambda bot, uid, message, next_allowed: sent.append(uid) or (True, next_allowed),
    )

    result = broadcast_handler.send_confirmed_exchange_broadcast(
        object(),
        owner,
        now="2026-10-10T00:06:00Z",
    )

    assert result["status"] == "EXPIRED"
    assert sent == []
    assert db["exchange_broadcast_pending"][owner]["status"] == "EXPIRED"
    assert db["exchange_broadcast_audit"][-1]["status"] == "EXPIRED"



def test_voice_prepare_accepts_common_stt_article_and_politeness_variant(monkeypatch):
    owner = str(broadcast_handler.OWNER_TELEGRAM_ID)
    db = _broadcast_db()

    monkeypatch.setattr(broadcast_handler.state_manager, "atomic_update", lambda mutate: mutate(db))
    monkeypatch.setattr(broadcast_handler.state_manager, "load_db", lambda: db)

    answer = broadcast_handler.route_exchange_broadcast_voice(
        object(),
        _voice_message(int(owner)),
        "תכין בבקשה הודעת ברודקאסט למסחר הפנימי",
        now="2026-10-10T00:00:00Z",
    )

    assert "תצוגה מקדימה בלבד" in answer
    assert "לא נשלחה הודעה לאף משתמש" in answer
    assert db["exchange_broadcast_pending"][owner]["status"] == "PENDING_CONFIRMATION"
    assert db["exchange_broadcast_audit"] == []


def test_voice_confirmation_accepts_common_stt_article_variant(monkeypatch):
    owner = str(broadcast_handler.OWNER_TELEGRAM_ID)
    called = []

    def confirm(bot, uid, *, now=None):
        called.append((uid, now))
        return {"status": "SENT", "sent": 1, "failed": 0, "target_count": 1}

    monkeypatch.setattr(broadcast_handler, "send_confirmed_exchange_broadcast", confirm)

    answer = broadcast_handler.route_exchange_broadcast_voice(
        object(),
        _voice_message(int(owner)),
        "אני מאשר לשלוח את הברודקאסט למסחר הפנימי",
        now="2026-10-10T00:00:01Z",
    )

    assert called == [(owner, "2026-10-10T00:00:01Z")]
    assert answer
