from types import SimpleNamespace

import handlers.natural_chat as natural_chat
import handlers.broadcast_handler as broadcast_handler
import core.system_checks as system_checks


OWNER = int(broadcast_handler.OWNER_TELEGRAM_ID)


class FakeBot:
    def __init__(self):
        self.sent = []
        self.handler = None

    def message_handler(self, **kwargs):
        def decorator(fn):
            self.handler = fn
            return fn
        return decorator

    def send_chat_action(self, chat_id, action):
        return None

    def send_message(self, chat_id, text, **kwargs):
        self.sent.append((chat_id, text, kwargs))


def _message(text, *, uid=OWNER, chat_type="private"):
    return SimpleNamespace(
        from_user=SimpleNamespace(id=uid, is_bot=False),
        chat=SimpleNamespace(id=uid, type=chat_type),
        text=text,
    )


def _green_exchange_check():
    return {
        "ok": True,
        "execution_ready": True,
        "public_gate": "OPEN",
        "verdict": "OPEN",
        "public_ready": True,
        "order_book_integrity": True,
        "trade_integrity": True,
        "money_invariants": True,
        "detail": "public state clean",
    }


def test_natural_text_exchange_broadcast_question_uses_fresh_read_only_check(monkeypatch):
    db = {
        "users": {str(OWNER): {}},
        "exchange_orders": {},
        "exchange_trades": [],
        "exchange_requests": {},
    }
    monkeypatch.setattr(broadcast_handler.state_manager, "load_db", lambda: db)
    monkeypatch.setattr(
        system_checks, "check_exchange_for_execution", lambda snapshot: _green_exchange_check()
    )
    llm_calls = []
    monkeypatch.setattr(
        natural_chat, "route", lambda text, uid: llm_calls.append((text, uid)) or "LLM guessed it was ready"
    )

    bot = FakeBot()
    natural_chat.register(bot)
    bot.handler(_message("אפשר כבר לשלוח ברודקאסט למסחר פנימי?"))

    assert llm_calls == []
    assert len(bot.sent) == 1
    answer = bot.sent[0][1]
    assert "READ ONLY" in answer
    assert "OPEN" in answer
    assert "לא נשלחה הודעה" in answer
    assert "exchange_broadcast_pending" not in db


def test_plain_text_broadcast_confirmation_is_not_an_authorization(monkeypatch):
    db = {
        "users": {str(OWNER): {}},
        "exchange_orders": {},
        "exchange_trades": [],
        "exchange_requests": {},
    }
    monkeypatch.setattr(broadcast_handler.state_manager, "load_db", lambda: db)
    llm_calls = []
    monkeypatch.setattr(
        natural_chat, "route", lambda text, uid: llm_calls.append((text, uid)) or "LLM answer"
    )

    bot = FakeBot()
    natural_chat.register(bot)
    bot.handler(_message("אשר ושלח ברודקאסט למסחר פנימי"))

    assert llm_calls == []
    assert len(bot.sent) == 1
    assert "קולית" in bot.sent[0][1] or "הודעה קולית" in bot.sent[0][1]
    assert "exchange_broadcast_pending" not in db
    assert "exchange_broadcast_audit" not in db
