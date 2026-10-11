import types

import handlers.broadcast_handler as target


class FakeBot:
    def __init__(self, scripted=None):
        self.scripted = list(scripted or [])
        self.sent = []
        self.replies = []

    def message_handler(self, commands):
        def decorator(fn):
            self.broadcast_cmd = fn
            return fn
        return decorator

    def send_message(self, uid, message):
        self.sent.append((uid, message))
        if self.scripted:
            action = self.scripted.pop(0)
            if isinstance(action, Exception):
                raise action

    def reply_to(self, message, text):
        self.replies.append((message, text))


def test_retry_after_parsing():
    class RateLimitedError(Exception):
        def __init__(self):
            self.result_json = {"parameters": {"retry_after": 7}}

    assert target._retry_after_seconds(RateLimitedError()) == 7.0


def test_broadcast_is_paced_and_owner_only(monkeypatch):
    bot = FakeBot()
    target.register(bot)

    clock = iter([0.0, 0.01, 0.05, 0.06, 0.10, 0.11])
    sleeps = []
    monkeypatch.setattr(target.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(target.time, "sleep", lambda value: sleeps.append(value))
    monkeypatch.setattr(
        target.state_manager,
        "load_db",
        lambda: {"users": {"1": {}, "2": {}}},
    )

    owner_message = types.SimpleNamespace(
        from_user=types.SimpleNamespace(id=target.OWNER_TELEGRAM_ID),
        text="/broadcast hello",
    )
    bot.broadcast_cmd(owner_message)

    assert bot.sent == [("1", "hello"), ("2", "hello")]
    assert any(value > 0 for value in sleeps)
    assert bot.replies[-1][1] == "✅ Broadcast sent to 2 users.\nFailed: 0"


def test_non_owner_is_rejected(monkeypatch):
    bot = FakeBot()
    target.register(bot)

    loaded = []
    monkeypatch.setattr(
        target.state_manager,
        "load_db",
        lambda: loaded.append(True) or {"users": {}},
    )

    message = types.SimpleNamespace(
        from_user=types.SimpleNamespace(id=12345),
        text="/broadcast hello",
    )
    bot.broadcast_cmd(message)

    assert bot.replies == [(message, "⛔ OWNER only")]
    assert loaded == []


def test_exchange_status_claim_is_refused_by_generic_broadcast(monkeypatch):
    bot = FakeBot()
    target.register(bot)

    loaded = []
    monkeypatch.setattr(
        target.state_manager,
        "load_db",
        lambda: loaded.append(True) or {"users": {"1": {}}},
    )
    message = types.SimpleNamespace(
        from_user=types.SimpleNamespace(id=target.OWNER_TELEGRAM_ID),
        text="/broadcast 🟢 SLH OS — המסחר הפנימי פתוח",
    )

    bot.broadcast_cmd(message)

    assert bot.sent == []
    assert loaded == []
    assert len(bot.replies) == 1
    assert "קולי" in bot.replies[0][1]



def test_broadcast_status_is_read_only_and_never_sends(monkeypatch):
    bot = FakeBot()
    target.register(bot)
    monkeypatch.setattr(
        target.state_manager,
        "load_db",
        lambda: {
            "users": {"1": {}},
            "exchange_broadcast_pending": {},
            "exchange_broadcast_audit": [],
        },
    )
    monkeypatch.setattr(
        target,
        "_fresh_exchange_check",
        lambda db: {
            "execution_ready": True,
            "public_gate": "OPEN",
            "verdict": "OPEN",
            "public_ready": True,
            "order_book_integrity": True,
            "trade_integrity": True,
            "money_invariants": True,
            "detail": "public state clean",
        },
    )
    message = types.SimpleNamespace(
        from_user=types.SimpleNamespace(id=target.OWNER_TELEGRAM_ID),
        text="/broadcast status",
    )

    bot.broadcast_cmd(message)

    assert bot.sent == []
    assert len(bot.replies) == 1
    assert "READ ONLY" in bot.replies[0][1]
    assert "OPEN" in bot.replies[0][1]



def _exchange_broadcast_db(users, audit=None):
    import hashlib

    return {
        "users": {str(uid): {} for uid in users},
        "exchange_broadcast_pending": {},
        "exchange_broadcast_audit": list(audit or []),
    }


def _partial_audit(*, draft_id, target_count, sent, failed, failed_recipient_uids=None):
    import hashlib

    return {
        "draft_id": draft_id,
        "initiated_by": str(target.OWNER_TELEGRAM_ID),
        "status": "PARTIAL",
        "target_count": target_count,
        "sent": sent,
        "failed": failed,
        "failed_recipient_uids": failed_recipient_uids,
        "audience_sha256": "previous-hash",
        "message_sha256": hashlib.sha256(target.EXCHANGE_BROADCAST_TEXT.encode("utf-8")).hexdigest(),
    }


def test_exchange_broadcast_retry_preview_targets_only_known_failed_recipients(monkeypatch):
    failed = _partial_audit(
        draft_id="partial-1",
        target_count=4,
        sent=2,
        failed=2,
        failed_recipient_uids=["2", "4"],
    )
    db = _exchange_broadcast_db(["1", "2", "3", "4"], [failed])
    monkeypatch.setattr(target.state_manager, "atomic_update", lambda mutate: mutate(db))

    result = target.prepare_exchange_broadcast(str(target.OWNER_TELEGRAM_ID))

    assert result["status"] == "PREPARED"
    assert result["target_count"] == 2
    pending = db["exchange_broadcast_pending"][str(target.OWNER_TELEGRAM_ID)]
    assert pending["audience_scope"] == "failed_only"
    assert pending["retry_of_draft_id"] == "partial-1"
    assert pending["requires_duplicate_ack"] is False


def test_exchange_broadcast_legacy_partial_preview_requires_duplicate_ack(monkeypatch):
    failed = _partial_audit(
        draft_id="legacy-partial",
        target_count=32,
        sent=27,
        failed=5,
    )
    db = _exchange_broadcast_db([str(i) for i in range(1, 33)], [failed])
    monkeypatch.setattr(target.state_manager, "atomic_update", lambda mutate: mutate(db))

    result = target.prepare_exchange_broadcast(str(target.OWNER_TELEGRAM_ID))

    assert result["status"] == "PREPARED"
    assert result["target_count"] == 32
    pending = db["exchange_broadcast_pending"][str(target.OWNER_TELEGRAM_ID)]
    assert pending["audience_scope"] == "all"
    assert pending["requires_duplicate_ack"] is True
    assert pending["previous_sent"] == 27
    assert pending["previous_failed"] == 5


def test_legacy_partial_confirmation_without_duplicate_ack_sends_nothing(monkeypatch):
    failed = _partial_audit(
        draft_id="legacy-partial",
        target_count=2,
        sent=1,
        failed=1,
    )
    db = _exchange_broadcast_db(["1", "2"], [failed])
    uid = str(target.OWNER_TELEGRAM_ID)
    db["exchange_broadcast_pending"][uid] = {
        "draft_id": "retry-1",
        "uid": uid,
        "status": "PENDING_CONFIRMATION",
        "expires_at": "2099-01-01T00:00:00+00:00",
        "target_count": 2,
        "audience_sha256": target._broadcast_audience_hash(["1", "2"]),
        "message_sha256": failed["message_sha256"],
        "audience_scope": "all",
        "requires_duplicate_ack": True,
        "previous_sent": 1,
        "previous_failed": 1,
    }
    monkeypatch.setattr(target.state_manager, "load_db", lambda: db)
    monkeypatch.setattr(target.state_manager, "atomic_update", lambda mutate: mutate(db))
    monkeypatch.setattr(target, "_fresh_exchange_check", lambda _db: {
        "execution_ready": True,
        "public_gate": "OPEN",
        "verdict": "OPEN",
        "public_ready": True,
        "order_book_integrity": True,
        "trade_integrity": True,
        "money_invariants": True,
        "detail": "public state clean",
    })
    bot = FakeBot()

    result = target.send_confirmed_exchange_broadcast(bot, uid)

    assert result["status"] == "DUPLICATE_ACK_REQUIRED"
    assert bot.sent == []
    assert db["exchange_broadcast_pending"][uid]["status"] == "PENDING_CONFIRMATION"



def test_exchange_broadcast_partial_persists_failed_recipient_ids(monkeypatch):
    import hashlib

    uid = str(target.OWNER_TELEGRAM_ID)
    message_hash = hashlib.sha256(target.EXCHANGE_BROADCAST_TEXT.encode("utf-8")).hexdigest()
    db = _exchange_broadcast_db(["1", "2"])
    db["exchange_broadcast_pending"][uid] = {
        "draft_id": "fresh-draft",
        "uid": uid,
        "status": "PENDING_CONFIRMATION",
        "created_at": "2026-10-11T10:00:00+00:00",
        "expires_at": "2099-01-01T00:00:00+00:00",
        "target_count": 2,
        "audience_sha256": target._broadcast_audience_hash(["1", "2"]),
        "message_sha256": message_hash,
        "audience_scope": "all",
        "requires_duplicate_ack": False,
    }
    monkeypatch.setattr(target.state_manager, "load_db", lambda: db)
    monkeypatch.setattr(target.state_manager, "atomic_update", lambda mutate: mutate(db))
    monkeypatch.setattr(target, "_fresh_exchange_check", lambda _db: {
        "execution_ready": True,
        "public_gate": "OPEN",
        "verdict": "OPEN",
        "public_ready": True,
        "order_book_integrity": True,
        "trade_integrity": True,
        "money_invariants": True,
        "detail": "public state clean",
    })
    bot = FakeBot([None, RuntimeError("blocked")])

    result = target.send_confirmed_exchange_broadcast(bot, uid)

    assert result["status"] == "PARTIAL"
    assert result["sent"] == 1
    assert result["failed"] == 1
    assert bot.sent == [("1", target.EXCHANGE_BROADCAST_TEXT), ("2", target.EXCHANGE_BROADCAST_TEXT)]
    audit = db["exchange_broadcast_audit"][-1]
    assert audit["failed_recipient_uids"] == ["2"]
    assert audit["audience_scope"] == "all"
