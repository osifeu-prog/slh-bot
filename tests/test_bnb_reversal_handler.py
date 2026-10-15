from types import SimpleNamespace
from unittest.mock import patch

from handlers import system_checks_handler as target

OWNER_UID = "8789977826"
TX = "0x" + "ab" * 32


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


def _message(text, *, uid=OWNER_UID, chat_type="private"):
    return SimpleNamespace(
        from_user=SimpleNamespace(id=int(uid)),
        chat=SimpleNamespace(type=chat_type),
        text=text,
    )


def _register(monkeypatch):
    bot = FakeBot()
    monkeypatch.setattr(target, "is_owner", lambda uid: str(uid) == OWNER_UID)
    target._PENDING_BNB_REVERSALS.clear()
    target.register(bot)
    return bot


def test_prepare_is_owner_only_private_and_creates_read_only_confirmation(monkeypatch):
    bot = _register(monkeypatch)
    preview = {
        "status": "PREPARED",
        "scope": "read_only",
        "source_ledger_index": 209,
        "tx_suffix": "caa496eb",
        "amount_reversed": 10.0,
        "balance_before": 30.072775,
        "balance_after": 20.072775,
        "expected_current_balance": "30.072775",
        "gate_remained_closed": True,
        "database_changed": False,
        "settlement_executed": False,
    }

    with patch(
        "core.credit_adjustment_service.preview_invalid_bnb_deposit_reversal",
        return_value=preview,
    ):
        bot.handlers["bnb_reverse_prepare"](_message(f"/bnb_reverse_prepare {TX}"))

    assert "DB changed: NO" in bot.replies[-1]
    assert "Projected balance: 20.072775 Credits" in bot.replies[-1]
    code = bot.replies[-1].split("/bnb_reverse_confirm ")[1].split()[0]
    assert target._PENDING_BNB_REVERSALS[code]["actor_uid"] == OWNER_UID
    assert target._PENDING_BNB_REVERSALS[code]["expected_current_balance"] == "30.072775"

    bot.handlers["bnb_reverse_prepare"](
        _message(f"/bnb_reverse_prepare {TX}", chat_type="group")
    )
    assert "שיחה פרטית" in bot.replies[-1]


def test_confirmation_consumes_one_time_code_and_calls_atomic_service(monkeypatch):
    bot = _register(monkeypatch)
    preview = {
        "status": "PREPARED",
        "source_ledger_index": 209,
        "tx_suffix": "caa496eb",
        "amount_reversed": 10.0,
        "balance_before": 30.072775,
        "balance_after": 20.072775,
        "expected_current_balance": "30.072775",
        "gate_remained_closed": True,
    }
    with patch(
        "core.credit_adjustment_service.preview_invalid_bnb_deposit_reversal",
        return_value=preview,
    ):
        bot.handlers["bnb_reverse_prepare"](_message(f"/bnb_reverse_prepare {TX}"))
    code = bot.replies[-1].split("/bnb_reverse_confirm ")[1].split()[0]

    applied = {
        "status": "APPLIED",
        "tx_hash": TX,
        "amount_reversed": 10.0,
        "balance_before": 30.072775,
        "balance_after": 20.072775,
        "gate_remained_closed": True,
    }
    with patch(
        "core.credit_adjustment_service.reverse_invalid_bnb_deposit",
        return_value=applied,
    ) as execute:
        bot.handlers["bnb_reverse_confirm"](
            _message(f"/bnb_reverse_confirm {code}")
        )
        execute.assert_called_once_with(
            actor_uid=OWNER_UID,
            uid=OWNER_UID,
            tx_hash=TX.lower(),
            expected_current_balance="30.072775",
            now=execute.call_args.kwargs["now"],
        )

        # A consumed confirmation cannot execute twice.
        bot.handlers["bnb_reverse_confirm"](
            _message(f"/bnb_reverse_confirm {code}")
        )
        assert execute.call_count == 1

    assert "BNB ACCOUNTING CORRECTION APPLIED" in bot.replies[-2]
    assert "Public BNB gate remained CLOSED" in bot.replies[-2]
    assert "invalid or not issued" in bot.replies[-1].lower()


def test_non_owner_cannot_prepare_or_confirm(monkeypatch):
    bot = _register(monkeypatch)
    bot.handlers["bnb_reverse_prepare"](
        _message(f"/bnb_reverse_prepare {TX}", uid="5010371391")
    )
    assert "OWNER ONLY" in bot.replies[-1]

    bot.handlers["bnb_reverse_confirm"](
        _message("/bnb_reverse_confirm any-code", uid="5010371391")
    )
    assert "OWNER ONLY" in bot.replies[-1]



def test_prepare_auto_discovers_a_unique_self_transfer_and_still_requires_confirmation(monkeypatch):
    bot = _register(monkeypatch)
    db = {
        "ledger": [{
            "uid": OWNER_UID,
            "reason": "bnb:deposit",
            "amount": 10.0,
            "meta": {
                "tx_hash": TX,
                "from": "0x1111111111111111111111111111111111111111",
                "to": "0x1111111111111111111111111111111111111111",
            },
        }],
    }
    preview = {
        "status": "PREPARED",
        "scope": "read_only",
        "source_ledger_index": 209,
        "tx_suffix": TX[-8:],
        "amount_reversed": 10.0,
        "balance_before": 30.072775,
        "balance_after": 20.072775,
        "expected_current_balance": "30.072775",
        "gate_remained_closed": True,
        "database_changed": False,
        "settlement_executed": False,
    }

    with patch("state_manager.load_db", return_value=db), patch(
        "core.credit_adjustment_service.preview_invalid_bnb_deposit_reversal",
        return_value=preview,
    ) as run_preview:
        bot.handlers["bnb_reverse_prepare"](_message("/bnb_reverse_prepare"))

    run_preview.assert_called_once_with(actor_uid=OWNER_UID, uid=OWNER_UID, tx_hash=TX.lower())
    assert "Discovery: AUTO" in bot.replies[-1]
    assert "DB changed: NO" in bot.replies[-1]
    code = bot.replies[-1].split("/bnb_reverse_confirm ")[1].split()[0]
    assert target._PENDING_BNB_REVERSALS[code]["tx_hash"] == TX.lower()
    assert target._PENDING_BNB_REVERSALS[code]["expected_current_balance"] == "30.072775"


def test_prepare_auto_discovery_fails_closed_for_zero_or_multiple_candidates(monkeypatch):
    bot = _register(monkeypatch)
    with patch("state_manager.load_db", return_value={"ledger": []}):
        bot.handlers["bnb_reverse_prepare"](_message("/bnb_reverse_prepare"))
    assert "לא נמצאה רשומת" in bot.replies[-1]
    assert not target._PENDING_BNB_REVERSALS

    db = {
        "ledger": [
            {
                "uid": OWNER_UID,
                "reason": "bnb:deposit",
                "meta": {
                    "tx_hash": TX,
                    "from": "0x1111111111111111111111111111111111111111",
                    "to": "0x1111111111111111111111111111111111111111",
                },
            },
            {
                "uid": OWNER_UID,
                "reason": "bnb:deposit",
                "meta": {
                    "tx_hash": "0x" + "cd" * 32,
                    "from": "0x2222222222222222222222222222222222222222",
                    "to": "0x2222222222222222222222222222222222222222",
                },
            },
        ],
    }
    with patch("state_manager.load_db", return_value=db):
        bot.handlers["bnb_reverse_prepare"](_message("/bnb_reverse_prepare"))
    assert "נמצאו 2 מועמדים" in bot.replies[-1]
    assert "אין בחירה אוטומטית" in bot.replies[-1]
    assert not target._PENDING_BNB_REVERSALS
